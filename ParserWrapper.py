#!/usr/bin/env python3
import sys


def load_parser_logic(conf_file: str):
    """
    Loads parser logic from the provided configuration file.
    The configuration file must define a function named 'determine_event_action'
    which accepts an event type (str) and returns a string.
    """
    conf_globals = {}
    try:
        with open(conf_file, 'r') as f:
            code = f.read()
        exec(code, conf_globals)
    except Exception as e:
        print(f"Error loading parser configuration: {e}")
        sys.exit(1)

    if 'determine_event_action' not in conf_globals:
        print("Error: The configuration file must define a function named 'determine_event_action'.")
        sys.exit(1)

    return conf_globals['determine_event_action']


def process_event_types(file_path: str, determine_event_action) -> list:
    """
    Reads event types from the given file and returns a list of those that
    produce an 'unknown' event action using the provided determine_event_action function.
    """
    try:
        with open(file_path, 'r') as f:
            event_types = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        sys.exit(1)

    unknown_events = [evt for evt in event_types if determine_event_action(evt) == "unknown"]
    return unknown_events


def main():
    if len(sys.argv) != 3:
        print("Usage: python wrapper.py <parser_conf_file> <event_types_file>")
        sys.exit(1)

    parser_conf_file = sys.argv[1]
    event_types_file = sys.argv[2]

    # Load the parser logic from the configuration file.
    determine_event_action = load_parser_logic(parser_conf_file)

    # Process the event types using the loaded logic.
    unknown_events = process_event_types(event_types_file, determine_event_action)

    print("Event types producing an 'unknown' event_action:")
    for event in unknown_events:
        print(event)


if __name__ == "__main__":
    main()
