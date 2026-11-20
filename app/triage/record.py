from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# 1. The fields we collect for the chest pain use case
# ---------------------------------------------------------------------------
CHEST_PAIN_FIELDS = (
    "symptom",
    "duration",
    "severity",
    "location",
    "radiation",
    "progression",
    "medical_history",
)

# One place that describes each field. Used for prompts and fallback questions.
# To add fever/headache later, you would add a similar table for them.
FIELD_INFO = {
    "symptom": {
        "about": "what the main problem or symptom is",
        "fallback": "What is the main problem that is bothering you?",
    },
    "duration": {
        "about": "how long the symptom has been going on",
        "fallback": "How long have you had this?",
    },
    "severity": {
        "about": "how strong the pain is, on a scale from 1 to 10",
        "fallback": "On a scale from 1 to 10, how strong is the pain?",
    },
    "location": {
        "about": "where exactly in the body the pain is",
        "fallback": "Where exactly do you feel it?",
    },
    "radiation": {
        "about": "whether the pain spreads to other parts, like the arm, jaw or back",
        "fallback": "Does the pain spread anywhere, like your arm, jaw or back?",
    },
    "progression": {
        "about": "whether it is getting better, worse, or staying the same",
        "fallback": "Is it getting better, worse, or staying the same?",
    },
    "medical_history": {
        "about": "any relevant medical conditions, like heart or blood pressure problems",
        "fallback": "Do you have any medical conditions, like heart or blood pressure problems?",
    },
}


# ---------------------------------------------------------------------------
# 2. One slot = status + value
#    Why not just None?  Because None cannot tell "not asked yet" apart from
#    "asked, patient cannot answer".  Mixing them causes infinite re-asking.
# ---------------------------------------------------------------------------
class SlotStatus(str, Enum):
    UNKNOWN = "unknown"
    VALUE = "value"
    UNAVAILABLE = "unavailable"


class Slot(BaseModel):
    status: SlotStatus = SlotStatus.UNKNOWN
    value: Optional[Union[str, int]] = None

    @property
    def resolved(self) -> bool:
        return self.status != SlotStatus.UNKNOWN


# ---------------------------------------------------------------------------
# 3. RecordUpdate = what the extractor returns after ONE patient turn.
#    Instructor reads the Field(description=...) texts and shows them to the
#    LLM, so write them carefully. Every field is Optional: the patient
#    usually gives only a part of the information in one sentence.
# ---------------------------------------------------------------------------
class RecordUpdate(BaseModel):
    symptom: Optional[str] = Field(
        None, description="Main symptom in simple words, e.g. 'chest pain'. null if not stated."
    )
    duration: Optional[str] = Field(
        None, description="How long it has lasted, e.g. '3 days'. null if not stated."
    )
    severity: Optional[int] = Field(
        None,
        ge=1,
        le=10,
        description=(
            "Pain strength from 1 to 10. Only fill if the patient gave a number "
            "or a clear equivalent. Vague words like 'pretty bad' -> null."
        ),
    )
    location: Optional[str] = Field(
        None, description="Where in the body, e.g. 'center of chest'. null if not stated."
    )
    radiation: Optional[str] = Field(
        None,
        description=(
            "Where the pain spreads to, e.g. 'left arm'. "
            "Use 'none' if the patient says it does not spread. null if not stated."
        ),
    )
    progression: Optional[str] = Field(
        None,
        description="'getting worse', 'getting better', 'staying the same' or 'comes and goes'. null if not stated.",
    )
    medical_history: Optional[str] = Field(
        None,
        description=(
            "Relevant medical conditions, e.g. 'high blood pressure'. "
            "Use 'none' if the patient says they have none. null if not stated."
        ),
    )
    cannot_answer: list[str] = Field(
        default_factory=list,
        description=(
            "Names of fields the patient said they do not know or cannot answer "
            "(e.g. 'I don't know how long'). Use only the field names above."
        ),
    )

    @field_validator("cannot_answer")
    @classmethod
    def keep_only_known_fields(cls, names: list[str]) -> list[str]:
        # LLM output is untrusted input: drop anything that is not a real field.
        return [n for n in names if n in CHEST_PAIN_FIELDS]


# ---------------------------------------------------------------------------
# 4. The record itself
# ---------------------------------------------------------------------------
class PatientRecord(BaseModel):
    symptom: Slot = Field(default_factory=Slot)
    duration: Slot = Field(default_factory=Slot)
    severity: Slot = Field(default_factory=Slot)
    location: Slot = Field(default_factory=Slot)
    radiation: Slot = Field(default_factory=Slot)
    progression: Slot = Field(default_factory=Slot)
    medical_history: Slot = Field(default_factory=Slot)

    # Audit trail: every time a value is set or corrected we log it.
    changes: list[dict] = Field(default_factory=list)

    def slots(self) -> dict[str, Slot]:
        return {name: getattr(self, name) for name in CHEST_PAIN_FIELDS}

    def missing_fields(self) -> list[str]:
        """Names of fields that are still UNKNOWN (not resolved)."""
        return [name for name, slot in self.slots().items() if not slot.resolved]

    def is_complete(self) -> bool:
        return not self.missing_fields()

    def value_of(self, name: str) -> Optional[Union[str, int]]:
        slot = getattr(self, name)
        return slot.value if slot.status == SlotStatus.VALUE else None

    def mark_unavailable(self, name: str) -> bool:
        """Patient cannot answer. Only affects UNKNOWN slots (never erases a known value)."""
        slot = getattr(self, name)
        if slot.status == SlotStatus.UNKNOWN:
            setattr(self, name, Slot(status=SlotStatus.UNAVAILABLE))
            return True
        return False

    def apply_update(self, update: RecordUpdate) -> list[str]:
        """
        Merge one patient turn into the record. Returns the names that changed.

        Rules (our design decisions):
        - null in the update means "no new info" -> never erases anything.
        - A new value overwrites the old one (patient corrected themselves),
          and the change is logged in `changes`.
        - Applying the same update twice gives the same record (idempotent),
          which matters because Pipecat can deliver the same turn twice.
        - cannot_answer only applies to UNKNOWN slots.
        """
        changed: list[str] = []

        for name in CHEST_PAIN_FIELDS:
            new_value = getattr(update, name)
            if new_value is None:
                continue
            if isinstance(new_value, str):
                new_value = new_value.strip()
                if not new_value:
                    continue

            slot = getattr(self, name)
            if slot.status == SlotStatus.VALUE and slot.value == new_value:
                continue  # nothing new

            old_value = slot.value if slot.status == SlotStatus.VALUE else None
            setattr(self, name, Slot(status=SlotStatus.VALUE, value=new_value))
            self.changes.append({"field": name, "old": old_value, "new": new_value})
            changed.append(name)

        for name in update.cannot_answer:
            if self.mark_unavailable(name):
                changed.append(name)

        return changed