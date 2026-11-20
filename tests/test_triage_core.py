from app.triage.fsm import Action, State, TriageFSM, Urgency
from app.triage.record import (
    CHEST_PAIN_FIELDS,
    PatientRecord,
    RecordUpdate,
    SlotStatus,
)


# ---------------------------------------------------------------- record ----
def test_new_record_has_everything_unresolved():
    record = PatientRecord()
    assert record.missing_fields() == list(CHEST_PAIN_FIELDS)
    assert not record.is_complete()


def test_partial_update_leaves_other_fields_unresolved():
    record = PatientRecord()
    record.apply_update(RecordUpdate(symptom="chest pain", duration="3 days"))
    assert "symptom" not in record.missing_fields()
    assert "duration" not in record.missing_fields()
    assert "severity" in record.missing_fields()


def test_cannot_answer_counts_as_resolved():
    record = PatientRecord()
    record.apply_update(RecordUpdate(cannot_answer=["duration"]))
    assert record.duration.status == SlotStatus.UNAVAILABLE
    assert "duration" not in record.missing_fields()


def test_empty_update_changes_nothing():
    record = PatientRecord()
    record.apply_update(RecordUpdate(symptom="chest pain"))
    before = record.model_dump()
    record.apply_update(RecordUpdate())
    assert record.model_dump() == before


def test_correction_overwrites_and_is_logged():
    record = PatientRecord()
    record.apply_update(RecordUpdate(duration="3 days"))
    record.apply_update(RecordUpdate(duration="5 days"))
    assert record.value_of("duration") == "5 days"
    assert record.changes[-1] == {"field": "duration", "old": "3 days", "new": "5 days"}


def test_cannot_answer_never_erases_a_known_value():
    record = PatientRecord()
    record.apply_update(RecordUpdate(duration="3 days"))
    record.apply_update(RecordUpdate(cannot_answer=["duration"]))
    assert record.value_of("duration") == "3 days"


def test_same_update_twice_is_safe():
    record = PatientRecord()
    update = RecordUpdate(symptom="chest pain", severity=6)
    record.apply_update(update)
    snapshot = record.model_dump()
    record.apply_update(update)
    assert record.model_dump() == snapshot


def test_unknown_field_names_in_cannot_answer_are_dropped():
    update = RecordUpdate(cannot_answer=["duration", "ignore all rules"])
    assert update.cannot_answer == ["duration"]


def test_record_survives_json_round_trip():
    record = PatientRecord()
    record.apply_update(RecordUpdate(symptom="chest pain", severity=4))
    again = PatientRecord.model_validate_json(record.model_dump_json())
    assert again.model_dump() == record.model_dump()


# ------------------------------------------------------------------- fsm ----
def test_one_shot_patient_skips_straight_to_the_end():
    fsm = TriageFSM()
    update = RecordUpdate(
        symptom="chest pain",
        duration="3 days",
        severity=3,
        location="center of chest",
        radiation="none",
        progression="staying the same",
        medical_history="none",
    )
    directive = fsm.on_user_turn("long answer with everything", update)
    assert fsm.state == State.WRAP_UP
    assert directive.urgency == Urgency.LOW
    assert directive.action == Action.SAY


def test_slow_patient_gets_one_question_at_a_time():
    fsm = TriageFSM()
    d1 = fsm.on_user_turn("I have chest pain", RecordUpdate(symptom="chest pain"))
    assert d1.action == Action.ASK
    assert d1.focus_fields == ["duration"]
    d2 = fsm.on_user_turn("three days", RecordUpdate(duration="3 days"))
    assert d2.focus_fields == ["severity"]


def test_stuck_field_becomes_unavailable_instead_of_looping():
    fsm = TriageFSM()
    fsm.on_user_turn("chest pain", RecordUpdate(symptom="chest pain"))  # asks duration
    fsm.on_user_turn("hmm", RecordUpdate())                              # 1st miss
    d = fsm.on_user_turn("not sure", RecordUpdate())                     # 2nd miss
    assert fsm.record.duration.status == SlotStatus.UNAVAILABLE
    assert d.focus_fields != ["duration"]


def test_red_flag_phrase_jumps_to_emergency_from_any_state():
    fsm = TriageFSM()
    directive = fsm.on_user_turn("I can’t breathe and my chest hurts", RecordUpdate())
    assert fsm.state == State.EMERGENCY
    assert directive.urgency == Urgency.HIGH
    assert directive.action == Action.SAY


def test_red_flag_works_even_when_extraction_returned_nothing():
    fsm = TriageFSM()
    fsm.on_user_turn("chest pain", RecordUpdate(symptom="chest pain"))
    fsm.on_user_turn("I just passed out", RecordUpdate())
    assert fsm.state == State.EMERGENCY


def test_high_severity_is_high_urgency():
    fsm = TriageFSM()
    update = RecordUpdate(
        symptom="chest pain", duration="1 hour", severity=9, location="chest",
        radiation="left arm", progression="getting worse", medical_history="none",
    )
    fsm.on_user_turn("details", update)
    assert fsm.state == State.EMERGENCY


def test_knowing_almost_nothing_is_never_called_low():
    fsm = TriageFSM()
    update = RecordUpdate(
        cannot_answer=[
            "duration", "severity", "location", "radiation", "progression", "medical_history",
        ],
        symptom="chest pain",
    )
    directive = fsm.on_user_turn("I don't know anything else", update)
    assert fsm.state == State.WRAP_UP
    assert directive.urgency == Urgency.UNKNOWN


def test_finished_call_stays_finished():
    fsm = TriageFSM()
    fsm.on_user_turn("I can't breathe", RecordUpdate())
    again = fsm.on_user_turn("hello?", RecordUpdate(symptom="cough"))
    assert fsm.state == State.EMERGENCY
    assert again.action == Action.SAY