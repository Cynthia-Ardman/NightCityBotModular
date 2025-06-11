Translate Event Codes Script

This Python script extracts translation mappings from a configuration file and applies them to event codes provided in a separate file (or a single code). It is especially useful when you have a configuration (for example, an Okta configuration) with one or more translate { ... } blocks as well as conditional mappings (using if and set statements) that define mappings for event codes. The script then tells you which codes produce valid translations versus those that default to "unknown".

    Note: All lookups are performed in a case‑insensitive manner by converting keys to lower‑case.

Features

    Extracts Translation Mappings:
        Parses all translate { ... } blocks in a configuration file, handling nested braces to capture the entire mapping.
        Also extracts conditional mappings defined via if ('raw_event_data.eventType' == '...') { set { ... } }.

    Case‑Insensitive Matching:
    All keys are normalized to lower‑case so that event codes match regardless of case (e.g. mim.streamDevicesCSVDownload will match mim.streamdevicescsvdownload).

    Select & Combine Mappings:
    Filter which blocks to use by specifying a source filter (--src-filter), and merge mappings from multiple blocks if needed.

    Field Processing:
        Process a file with event codes (one per line) and print only the translated values that are not "unknown".
        Optionally print only event codes that produce "unknown".
        Optionally print only the field names (without the translation values).
        Optionally differentiate between fields that are explicitly mapped to "unknown" versus those that fall back to the default (using --diff-unknown).
        Optionally print only fields that produce default "unknown" (i.e. not explicitly mapped) using --only-default-unknown.

    Test Mode:
    Allows testing a single event code.

    Debug Output:
    With the --debug flag, the script prints detailed information about how the configuration file is parsed, how mappings are combined, and how lookups are performed.

Requirements

    Python 3.x

Usage

Run the script from the command line using the following syntax:

python3 TranslateEvents.py [OPTIONS] config_file

Required Argument

    config_file
    Path to the configuration file containing the translate blocks and conditional mappings.

Mutually Exclusive Options (choose one)

    --fields-file FILENAME
    A file that contains event codes (one per line) to process.

    --test-field "EVENT_CODE"
    Test a single event code.

Optional Flags

    --src-filter "STRING"
    Filter for the translate block's src field.
    Default: "raw_event_data.eventType"

    --debug
    Enable debug output (prints detailed processing information).

    --only-unknown
    Print only the event codes that produce the translation "unknown" (whether explicitly mapped or default).

    --fieldnames-only
    When printing output, print only the field names (without the translation value).

    --diff-unknown
    When an event code produces "unknown", append a marker:
        (explicit) if the event code is explicitly mapped to "unknown".
        (default) if the event code is not found in the mapping (thus falling back to the default).

    --only-default-unknown
    Print only those event codes that produce "unknown" because they were not explicitly defined in the mapping, excluding fields that are explicitly mapped to "unknown".

Examples

    Translate event codes from a file (default behavior):

    This will print only event codes with valid (non-"unknown") translations.

python3 TranslateEvents.py okta.conf --fields-file oktaevents.txt --src-filter "raw_event_data.eventType"

Print only event codes that produce "unknown" along with their translations:

python3 TranslateEvents.py okta.conf --fields-file oktaevents.txt --src-filter "raw_event_data.eventType" --only-unknown

Print only the field names (without translations) that produce "unknown":

python3 TranslateEvents.py okta.conf --fields-file oktaevents.txt --src-filter "raw_event_data.eventType" --only-unknown --fieldnames-only

Differentiate unknowns with markers:

Unknown fields explicitly mapped to "unknown" will be marked with (explicit) and those not found will be marked with (default).

python3 TranslateEvents.py okta.conf --fields-file oktaevents.txt --src-filter "raw_event_data.eventType" --only-unknown --diff-unknown

Print only default-unknown fields (i.e. not explicitly mapped to "unknown"):

python3 TranslateEvents.py okta.conf --fields-file oktaevents.txt --src-filter "raw_event_data.eventType" --only-unknown --only-default-unknown

Test a single event code with debug output:

    python3 TranslateEvents.py okta.conf --test-field "app.access_request.approver.approve" --src-filter "raw_event_data.eventType" --debug

How It Works

    Parsing the Configuration File:
    The script scans the provided configuration file for:
        translate { ... } blocks (extracting the src property, default value, and mapping dictionary).
        Conditional mapping blocks (using if and set statements) that check equality on 'raw_event_data.eventType' and assign a value for event.action. All keys are converted to lower‑case for case‑insensitive matching.

    Selecting & Combining Blocks:
    Using the --src-filter option, the script combines all translate blocks that match the provided source filter into a single mapping. It then merges in any conditional mappings so that both types of mappings are included.

    Processing Fields:
        If processing a file (--fields-file), the script reads each event code, converts it to lower‑case for lookup, and applies the mapping.
        Depending on the flags, it prints only non-"unknown" translations, only unknowns, or just the field names.
        In test mode (--test-field), it prints the result for a single event code.

    Debugging:
    When --debug is enabled, the script prints detailed information about each step, including how each translate block and conditional mapping is parsed, and the final combined mapping.

Troubleshooting

    No output or all "unknown":
    Ensure your event codes exactly match the keys defined in the configuration (they are compared case‑insensitively). Check for typos or differences in punctuation and spacing.

    File not found errors:
    Verify that the paths to your configuration file (e.g., okta.conf) and event codes file (e.g., oktaevents.txt) are correct.

    Use the debug flag (--debug) to see detailed processing logs to help diagnose issues.

License

This script is provided "as is" without any warranty. Use it at your own risk.