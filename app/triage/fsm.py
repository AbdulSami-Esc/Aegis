import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.triage.record import PatientRecord, RecordUpdate, SlotStatus

logger = logging.getLogger(__name__)


class State(str, Enum):
    COLLECT_SYMPTOM_DETAILS = "collect_symptom_details"  # information-gathering
    ASSESS_URGENCY = "assess_urgency"                    # decision-making
    EMERGENCY = "emergency"                              # terminal
    WRAP_UP = "wrap_up"                                  # terminal


class Urgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"  


class Action(str, Enum):
    ASK = "ask" 
    SAY = "say"  


@dataclass
class Directive:
    state: State
    action: Action
    focus_fields: list[str] = field(default_factory=list)
    scripted_text: str = ""
    urgency: Optional[Urgency] = None


RED_FLAG_PHRASES = (
    "can't breathe",
    "cannot breathe",
    "can not breathe",
    "not breathing",
    "unconscious",
    "passed out",
    "fainted",
    "crushing",
    "worst pain of my life",
    "blue lips",
)

NO_WORDS = {"none", "no", "nothing", "not at all"}

MAX_UNANSWERED = 2         
MIN_VALUES_TO_DECIDE = 3  

OPENING_TEXT = (
    "Hello, I am Aegis, a virtual triage assistant. "
    "This is a demo with synthetic data. What is bothering you today?"
)
EMERGENCY_TEXT = (
    "What you describe may be serious. Please call your local emergency "
    "number or go to the nearest emergency room right now."
)
WRAP_UP_TEXT = {
    Urgency.LOW: (
        "Thank you. Based on what you told me, this looks low urgency. "
        "Rest, and see a doctor if it continues or gets worse."
    ),
    Urgency.MEDIUM: (
        "Thank you. I recommend seeing a doctor today. "
        "If it gets worse or you feel faint or short of breath, call your local emergency number."
    ),
    Urgency.UNKNOWN: (
        "I could not collect enough information to judge this safely. "
        "If you are worried, please speak to a doctor soon, and call your "
        "local emergency number if it gets worse."
    ),
}


# ---------------------------------------------------------------------------
# The FSM
# ---------------------------------------------------------------------------
class TriageFSM:
    def __init__(self, record: Optional[PatientRecord] = None):
        self.record = record or PatientRecord()
        self.state = State.COLLECT_SYMPTOM_DETAILS
        self.urgency: Optional[Urgency] = None
        self._last_focus: list[str] = []
        self._unanswered: dict[str, int] = {}

    # ----- public API ------------------------------------------------------
    @property
    def is_finished(self) -> bool:
        return self.state in (State.EMERGENCY, State.WRAP_UP)

    def opening(self) -> Directive:
        return Directive(self.state, Action.SAY, scripted_text=OPENING_TEXT)

    def on_user_turn(self, user_text: str, update: RecordUpdate) -> Directive:
        """One patient turn in, one Directive out. Order matters."""
        if self.is_finished:
            return self._terminal_directive()

        # 1. Emergency check on the raw text. Deterministic, no LLM involved,
        #    works from any state, even if extraction failed.
        if self._has_red_flag(user_text):
            logger.warning("Red flag phrase detected -> EMERGENCY")
            self.state = State.EMERGENCY
            self.urgency = Urgency.HIGH
            return self._terminal_directive()

        # 2. Update the record with the new facts.
        changed = self.record.apply_update(update)
        logger.info("Record changed: %s", changed)

        # 3. Anti-loop: fields we asked about but never got an answer for.
        self._close_stuck_fields()

        # 4. Move through states until we need the patient again.
        return self._advance()

    # ----- internals -------------------------------------------------------
    def _has_red_flag(self, text: str) -> bool:
        clean = text.lower().replace("\u2019", "'")
        return any(phrase in clean for phrase in RED_FLAG_PHRASES)

    def _close_stuck_fields(self) -> None:
        for name in self._last_focus:
            if getattr(self.record, name).resolved:
                continue
            self._unanswered[name] = self._unanswered.get(name, 0) + 1
            if self._unanswered[name] >= MAX_UNANSWERED:
                self.record.mark_unavailable(name)
                logger.info("Field '%s' marked unavailable after %d asks", name, MAX_UNANSWERED)
        self._last_focus = []

    def _advance(self) -> Directive:
        while True:
            if self.state == State.COLLECT_SYMPTOM_DETAILS:
                missing = self.record.missing_fields()
                if missing:
                    focus = [missing[0]]  # one question at a time (voice)
                    self._last_focus = focus
                    return Directive(self.state, Action.ASK, focus_fields=focus)
                self.state = State.ASSESS_URGENCY

            elif self.state == State.ASSESS_URGENCY:
                self.urgency = self._assess_urgency()
                self.state = State.EMERGENCY if self.urgency == Urgency.HIGH else State.WRAP_UP

            else:
                return self._terminal_directive()

    def _assess_urgency(self) -> Urgency:
        values_known = sum(
            1 for slot in self.record.slots().values() if slot.status == SlotStatus.VALUE
        )
        if values_known < MIN_VALUES_TO_DECIDE:
            return Urgency.UNKNOWN  # never say "low" just because we know nothing

        severity = self.record.value_of("severity")
        severity = severity if isinstance(severity, int) else None

        radiation = self.record.value_of("radiation")
        radiates = isinstance(radiation, str) and radiation.strip().lower() not in NO_WORDS

        if severity is not None and severity >= 8:
            return Urgency.HIGH
        if radiates and severity is not None and severity >= 5:
            return Urgency.HIGH
        if (severity is not None and severity >= 5) or radiates:
            return Urgency.MEDIUM
        return Urgency.LOW

    def _terminal_directive(self) -> Directive:
        if self.state == State.EMERGENCY:
            return Directive(self.state, Action.SAY, scripted_text=EMERGENCY_TEXT, urgency=Urgency.HIGH)
        urgency = self.urgency or Urgency.UNKNOWN
        return Directive(self.state, Action.SAY, scripted_text=WRAP_UP_TEXT[urgency], urgency=urgency)