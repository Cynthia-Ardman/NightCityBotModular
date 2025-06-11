#!/usr/bin/env python3
import sys
from dsl_parser import parse_dsl, IfInstruction, RenameInstruction, TranslateInstruction

def apply_instructions(data: dict, instructions: list) -> dict:
    """
    Applies a list of DSLInstruction objects to the given data in order.
    Returns the modified data.
    """
    for instr in instructions:
        instr.apply(data)
    return data

def main():
    if len(sys.argv) != 3:
        print("Usage: python dsl_wrapper.py <parser.conf> <event_types.txt>")
        sys.exit(1)

    conf_file = sys.argv[1]
    event_types_file = sys.argv[2]

    # 1) Parse the DSL conf file to build instructions
    instructions = parse_dsl(conf_file)

    # 2) Read the event types from the text file
    try:
        with open(event_types_file, "r") as f:
            event_types = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: The file '{event_types_file}' was not found.")
        sys.exit(1)

    # 3) For each event type, create a minimal data structure and apply the DSL
    unknown_events = []
    for evt in event_types:
        # In the real system, you'd have a nested dictionary. We'll do something minimal:
        data = {
            "raw_event_data.eventType": evt,   # So 'translate { src = "raw_event_data.eventType" ... }' can find it
        }
        # apply DSL
        result = apply_instructions(data, instructions)

        # Check if we ended up with an event.action
        event_action = result.get("event.action", "unknown")
        if event_action == "unknown":
            unknown_events.append(evt)

    # 4) Print out the unknown ones
    print("Event types producing an 'unknown' event_action:")
    for ue in unknown_events:
        print(ue)

if __name__ == "__main__":
    main()
