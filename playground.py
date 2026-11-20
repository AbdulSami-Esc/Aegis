import asyncio
import logging

from app.triage.extractor import Extractor
from app.triage.fsm import TriageFSM
from app.triage.replier import Replier

logging.basicConfig(level=logging.WARNING)


async def main() -> None:
    fsm = TriageFSM()
    extractor = Extractor()
    replier = Replier()

    last_question = fsm.opening().scripted_text
    print(f"\nAEGIS: {last_question}\n")

    while not fsm.is_finished:
        text = input("PATIENT: ").strip()
        if not text:
            continue

        update = await extractor.extract(text, fsm.record, last_question)
        directive = fsm.on_user_turn(text, update)
        reply = await replier.reply(directive, text)
        last_question = reply

        print("  -- extracted :", update.model_dump(exclude_none=True, exclude_defaults=True))
        print("  -- state     :", fsm.state.value, "| urgency:", fsm.urgency)
        print("  -- missing   :", fsm.record.missing_fields())
        print(f"\nAEGIS: {reply}\n")

    print("---- final record ----")
    print(fsm.record.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())