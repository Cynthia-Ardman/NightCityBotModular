#!/usr/bin/env python3
import sys
import re
import argparse


def debug_print(debug, message):
    if debug:
        print(message)


def parse_translate_blocks(config_file, debug=False):
    """
    Parses the configuration file to extract all explicit translate blocks.
    Handles nested braces for the map block.
    Returns a list of dicts with keys:
      - 'src': the source field (e.g. 'raw_event_data.eventType')
      - 'default': the default translation value (or "unknown")
      - 'mapping': a dictionary of key-value translations (keys normalized to lower-case).
    """
    debug_print(debug, f"[parse_translate_blocks] Reading: {config_file}")
    try:
        with open(config_file, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"ERROR: Config file not found: {config_file}")
        sys.exit(1)
    blocks = []
    pos = 0
    while True:
        match = re.search(r"translate\s*{", content[pos:])
        if not match:
            debug_print(debug, "[parse_translate_blocks] No more 'translate {' blocks found.")
            break
        block_start = pos + match.start()
        start = pos + match.end()  # position after "translate {"
        brace_count = 1
        end = start
        while brace_count > 0 and end < len(content):
            if content[end] == '{':
                brace_count += 1
            elif content[end] == '}':
                brace_count -= 1
            end += 1
        block_content = content[block_start:end]
        debug_print(debug, "--------------------------------------------------")
        debug_print(debug, "[parse_translate_blocks] Found translate block:")
        debug_print(debug, block_content)
        debug_print(debug, "--------------------------------------------------")

        # Extract src property
        src_match = re.search(r"src\s*=\s*'([^']+)'", block_content)
        src = src_match.group(1) if src_match else None
        debug_print(debug, f"[parse_translate_blocks] src: {src}")

        # Extract default value, if any
        default_match = re.search(r"default\s*=\s*'([^']+)'", block_content)
        default_value = default_match.group(1) if default_match else "unknown"
        debug_print(debug, f"[parse_translate_blocks] default: {default_value}")

        # Extract the map block
        mapping = {}
        map_match = re.search(r"map\s*=\s*{", block_content)
        if map_match:
            map_start = map_match.end()
            brace_count_map = 1
            map_end = map_start
            while brace_count_map > 0 and map_end < len(block_content):
                if block_content[map_end] == '{':
                    brace_count_map += 1
                elif block_content[map_end] == '}':
                    brace_count_map -= 1
                map_end += 1
            map_content = block_content[map_match.end(): map_end - 1]
            debug_print(debug, "[parse_translate_blocks] map content:")
            debug_print(debug, map_content)

            # Extract key/value pairs (convert keys to lower-case)
            for key, value in re.findall(r"'([^']+)'\s*=\s*'([^']+)'", map_content):
                mapping[key.lower()] = value
                debug_print(debug, f"[parse_translate_blocks] Mapped '{key.lower()}' to '{value}'")

        blocks.append({
            'src': src,
            'default': default_value,
            'mapping': mapping
        })
        pos = end
    debug_print(debug, f"[parse_translate_blocks] Finished. Found {len(blocks)} translate block(s).")
    return blocks


def parse_conditional_mappings(config_file, debug=False):
    """
    Parses the configuration file for conditional mapping blocks that check
    'raw_event_data.eventType' for equality and then set a value for 'event.action'.
    Returns a dictionary of event code -> translation (with keys normalized to lower-case).
    """
    try:
        with open(config_file, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"ERROR: Config file not found: {config_file}")
        sys.exit(1)
    cond_map = {}
    # Regex finds if blocks that check equality on 'raw_event_data.eventType'
    pattern = r"if\s*\(\s*'raw_event_data\.eventType'\s*==\s*'([^']+)'\s*\)\s*{(.*?)}"
    matches = re.findall(pattern, content, re.DOTALL)
    debug_print(debug, f"[parse_conditional_mappings] Found {len(matches)} conditional blocks.")
    for event_code, inner_block in matches:
        # Look for a set statement that sets event.action
        set_pattern = r"set\s*{\s*dest\s*=\s*'event\.action'\s*,\s*value\s*=\s*'([^']+)'"
        set_matches = re.findall(set_pattern, inner_block)
        if set_matches:
            # Use the first occurrence; normalize the event code key to lower-case.
            cond_map[event_code.lower()] = set_matches[0]
            debug_print(debug, f"[parse_conditional_mappings] Mapping found: {event_code.lower()} -> {set_matches[0]}")
    return cond_map


def combine_blocks(blocks, src_filter, debug=False):
    """
    Combines all explicit translate blocks with the given src_filter into a single mapping.
    If a key appears in more than one block, later ones override earlier ones.
    Keys in the mapping are already normalized to lower-case.
    """
    debug_print(debug, f"[combine_blocks] Combining blocks for src_filter='{src_filter}'")
    combined_mapping = {}
    default_value = None
    for block in blocks:
        if block['src'] == src_filter:
            debug_print(debug, f"[combine_blocks] Using block with src={block['src']}, default={block['default']}")
            for k, v in block['mapping'].items():
                debug_print(debug, f"[combine_blocks]   {k} -> {v}")
            combined_mapping.update(block['mapping'])
            if default_value is None:
                default_value = block['default']
    if default_value is None:
        default_value = "unknown"
    debug_print(debug, f"[combine_blocks] Final default='{default_value}'")
    debug_print(debug, f"[combine_blocks] Final combined mapping has {len(combined_mapping)} entries.")
    return {'src': src_filter, 'default': default_value, 'mapping': combined_mapping}


def select_block(blocks, src_filter=None, debug=False):
    """
    If a src_filter is provided, combines all explicit blocks whose src matches the filter.
    Otherwise, returns the first block found.
    """
    debug_print(debug, f"[select_block] src_filter='{src_filter}'")
    if src_filter:
        matching_blocks = [b for b in blocks if b['src'] == src_filter]
        debug_print(debug, f"[select_block] Found {len(matching_blocks)} blocks with matching src.")
        if not matching_blocks:
            print(f"No translate blocks found with src '{src_filter}'")
            sys.exit(1)
        return combine_blocks(blocks, src_filter, debug)
    else:
        if not blocks:
            print("No translate blocks found in configuration file.")
            sys.exit(1)
        return blocks[0]


def process_fields(block, fields_file, debug=False, only_unknown=False, fieldnames_only=False, diff_unknown=False,
                   only_default_unknown=False):
    """
    Reads a file of fields (one per line) and prints the translation for each field.
    - If only_unknown is True, prints only fields whose translation is "unknown".
    - If fieldnames_only is True, prints only the field names (without the translation).
    - If diff_unknown is True and the translation is "unknown", appends a marker:
         (explicit) if the field is explicitly mapped to "unknown",
         (default) if the field is not found.
    - If only_default_unknown is True, prints only fields that produce "unknown" due to default (not explicitly mapped).
    Note: The lookup is done in a case-insensitive manner.
    """
    debug_print(debug, f"[process_fields] Reading fields from {fields_file}")
    found_any = False
    try:
        with open(fields_file, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"ERROR: Fields file not found: {fields_file}")
        sys.exit(1)

    for line in lines:
        field = line.strip()
        if not field:
            continue
        # Convert field to lower-case for lookup.
        field_lower = field.lower()
        if field_lower in block['mapping']:
            translation = block['mapping'][field_lower]
            unknown_marker = " (explicit)" if translation == "unknown" else ""
            explicit = True
        else:
            translation = block['default']
            unknown_marker = " (default)"
            explicit = False
        debug_print(debug,
                    f"[process_fields] Field='{field}' (lookup as '{field_lower}') => Translation='{translation}' (explicit: {explicit})")
        # Filtering logic:
        if only_unknown:
            if translation == "unknown":
                if only_default_unknown and explicit:
                    continue
                if fieldnames_only:
                    print(field + (unknown_marker if diff_unknown else ""))
                else:
                    print(f"{field} -> {translation}{(unknown_marker if diff_unknown else '')}")
                found_any = True
        else:
            if translation != "unknown":
                if fieldnames_only:
                    print(field)
                else:
                    print(f"{field} -> {translation}")
                found_any = True
    if not found_any:
        if only_unknown:
            print("[process_fields] No fields produced 'unknown' (with given filtering).")
        else:
            print("[process_fields] No fields with a mapping (non-unknown) were found.")


def test_field(block, test_field, debug=False, fieldnames_only=False, diff_unknown=False, only_default_unknown=False):
    """
    Tests a single field and prints its translation along with debug info.
    Applies the same filtering as process_fields.
    The lookup is done in a case-insensitive manner.
    """
    debug_print(debug, f"[test_field] Testing single field='{test_field}'")
    test_field_lower = test_field.lower()
    if test_field_lower in block['mapping']:
        translation = block['mapping'][test_field_lower]
        unknown_marker = " (explicit)" if translation == "unknown" else ""
        explicit = True
    else:
        translation = block['default']
        unknown_marker = " (default)"
        explicit = False
    if only_default_unknown and explicit:
        return
    if fieldnames_only:
        print(test_field + (unknown_marker if diff_unknown and translation == "unknown" else ""))
    else:
        print(
            f"Test field: {test_field} -> {translation}{(unknown_marker if diff_unknown and translation == 'unknown' else '')}")
    if translation == "unknown":
        debug_print(debug, "[test_field] This field is either explicitly mapped to 'unknown' or not found.")


def main():
    print("[main] Starting TranslateEvents.py ...")
    parser = argparse.ArgumentParser(description="Translate event codes using a configuration file.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--fields-file", help="File containing fields to translate (one per line)")
    group.add_argument("--test-field", help="Test a single field")
    parser.add_argument("config_file", help="Path to configuration file")
    parser.add_argument("--src-filter", help="Filter for the translate block's src field",
                        default="raw_event_data.eventType")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--only-unknown", action="store_true",
                        help="Print only fields that produce 'unknown'")
    parser.add_argument("--fieldnames-only", action="store_true",
                        help="Print only the field names (without translations)")
    parser.add_argument("--diff-unknown", action="store_true",
                        help="Differentiate unknown fields with markers: (explicit) vs (default)")
    parser.add_argument("--only-default-unknown", action="store_true",
                        help="Print only fields that produce 'unknown' due to default (not explicitly mapped)")
    args = parser.parse_args()

    print(f"[main] Arguments: config_file={args.config_file}, fields_file={args.fields_file}, "
          f"test_field={args.test_field}, src_filter={args.src_filter}, debug={args.debug}, "
          f"only_unknown={args.only_unknown}, fieldnames_only={args.fieldnames_only}, "
          f"diff_unknown={args.diff_unknown}, only_default_unknown={args.only_default_unknown}")

    # Parse explicit translate blocks.
    blocks = parse_translate_blocks(args.config_file, args.debug)
    debug_print(args.debug, f"[main] parse_translate_blocks returned {len(blocks)} block(s).")
    selected_block = select_block(blocks, args.src_filter, args.debug)

    # Parse conditional mappings (if blocks that set event.action).
    cond_map = parse_conditional_mappings(args.config_file, args.debug)
    debug_print(args.debug, f"[main] Conditional mappings found: {cond_map}")
    # Merge the conditional mappings (with keys normalized to lower-case) into the selected block's mapping.
    for k, v in cond_map.items():
        selected_block['mapping'][k] = v

    if args.test_field:
        test_field(selected_block, args.test_field, args.debug, args.fieldnames_only, args.diff_unknown,
                   args.only_default_unknown)
    elif args.fields_file:
        process_fields(selected_block, args.fields_file, args.debug, args.only_unknown, args.fieldnames_only,
                       args.diff_unknown, args.only_default_unknown)


if __name__ == '__main__':
    main()
