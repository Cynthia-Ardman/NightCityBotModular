#!/usr/bin/env python3
import sys
import re
import argparse


def debug_print(debug, message):
    if debug:
        print(message)


def norm_str(s):
    """Normalize a string by lowercasing and removing underscores."""
    return s.lower().replace("_", "")


def parse_translate_blocks(config_file, debug=False):
    """
    Parses the configuration file to extract explicit translate blocks.
    Handles nested braces for the map block.
    Returns a list of dicts with keys:
      - 'src': the source field (as defined in the block)
      - 'default': the default translation value (or "unknown")
      - 'mapping': a dictionary of key->value translations (keys normalized to lower-case).
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
        start = pos + match.end()
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
        src_match = re.search(r"src\s*=\s*'([^']+)'", block_content)
        src = src_match.group(1) if src_match else None
        debug_print(debug, f"[parse_translate_blocks] src: {src}")
        default_match = re.search(r"default\s*=\s*'([^']+)'", block_content)
        default_value = default_match.group(1) if default_match else "unknown"
        debug_print(debug, f"[parse_translate_blocks] default: {default_value}")
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
            for key, value in re.findall(r"'([^']+)'\s*=\s*'([^']+)'", map_content):
                mapping[key.lower()] = value
                debug_print(debug, f"[parse_translate_blocks] Mapped '{key.lower()}' to '{value}'")
        blocks.append({'src': src, 'default': default_value, 'mapping': mapping})
        pos = end
    debug_print(debug, f"[parse_translate_blocks] Finished. Found {len(blocks)} translate block(s).")
    return blocks


def parse_conditional_rules(config_file, src_filter, debug=False):
    """
    Parses the configuration file for conditional rules of the form:
      if ( 'FIELD' OP 'VALUE' ) { ... set { dest = 'event.action', value = 'MAPPED' } ... }
    Only rules where the normalized FIELD equals the normalized src_filter are extracted.
    Supports operators: ==, starts_with, contains.
    Returns a list of rules (each a dict with keys: operator, cond_value, mapping),
    with condition values normalized to lower-case.
    """
    try:
        with open(config_file, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"ERROR: Config file not found: {config_file}")
        sys.exit(1)
    rules = []
    pattern = r"if\s*\(\s*'([^']+)'\s*(==|starts_with|contains)\s*'([^']+)'\s*\)\s*{(.*?)}"
    matches = re.findall(pattern, content, re.DOTALL)
    debug_print(debug, f"[parse_conditional_rules] Found {len(matches)} conditional blocks.")
    for field, op, cond_val, block_content in matches:
        if norm_str(field) == norm_str(src_filter):
            set_pattern = r"set\s*{\s*dest\s*=\s*'event\.action'\s*,\s*value\s*=\s*'([^']+)'"
            set_matches = re.findall(set_pattern, block_content)
            if set_matches:
                rules.append({'operator': op, 'cond_value': cond_val.lower(), 'mapping': set_matches[0]})
                debug_print(debug,
                            f"[parse_conditional_rules] Rule: if {norm_str(field)} {op} {cond_val.lower()} then event.action = {set_matches[0]}")
    return rules


def apply_conditional_rules(field_value, cond_rules, debug=False):
    for rule in cond_rules:
        op = rule['operator']
        cond_val = rule['cond_value']
        mapping = rule['mapping']
        if op == "==":
            if field_value == cond_val:
                debug_print(debug, f"[apply_conditional_rules] Matched equality: {field_value} == {cond_val}")
                return mapping
        elif op == "starts_with":
            if field_value.startswith(cond_val):
                debug_print(debug,
                            f"[apply_conditional_rules] Matched starts_with: {field_value} starts with {cond_val}")
                return mapping
        elif op == "contains":
            if cond_val in field_value:
                debug_print(debug, f"[apply_conditional_rules] Matched contains: {field_value} contains {cond_val}")
                return mapping
    return None


def combine_blocks(blocks, src_filter, debug=False):
    debug_print(debug, f"[combine_blocks] Combining blocks for src_filter='{src_filter}'")
    combined_mapping = {}
    default_value = None
    for block in blocks:
        # For a specific src_filter (not ALL) use exact matching:
        if src_filter.upper() != "ALL":
            if block['src'] is not None and norm_str(block['src']) == norm_str(src_filter):
                debug_print(debug, f"[combine_blocks] Using block with src={block['src']}, default={block['default']}")
                combined_mapping.update(block['mapping'])
                if default_value is None:
                    default_value = block['default']
        else:
            # When src_filter is ALL, combine every block.
            if block['mapping']:
                combined_mapping.update(block['mapping'])
            if default_value is None:
                default_value = block['default']
    if default_value is None:
        default_value = "unknown"
    debug_print(debug, f"[combine_blocks] Final default='{default_value}'")
    debug_print(debug, f"[combine_blocks] Final combined mapping has {len(combined_mapping)} entries.")
    return {'src': src_filter, 'default': default_value, 'mapping': combined_mapping}


def print_all_mappings(blocks, cond_rules, diff_unknown=False):
    """
    Prints all explicit mappings from all translate blocks and then prints all conditional rules.
    """
    print("Explicit Translate Blocks:")
    for block in blocks:
        print(f"Src: {block['src']}  (Default: {block['default']})")
        if block['mapping']:
            for key, value in block['mapping'].items():
                print(f"  {key} -> {value}")
        else:
            print("  (No explicit mappings)")
        print()  # Blank line
    print("Conditional Rules:")
    if cond_rules:
        for rule in cond_rules:
            op = rule['operator']
            cond_val = rule['cond_value']
            mapping = rule['mapping']
            print(f"  If field {op} '{cond_val}' then event.action = {mapping}")
    else:
        print("  (No conditional rules)")


def select_block(blocks, src_filter, debug=False):
    """
    If src_filter is not "ALL", returns a combined mapping for blocks whose normalized src matches the normalized src_filter.
    Otherwise, returns a combination of all blocks.
    """
    if norm_str(src_filter) == "all":
        return combine_blocks(blocks, src_filter, debug)
    else:
        matching_blocks = [b for b in blocks if b['src'] is not None and norm_str(b['src']) == norm_str(src_filter)]
        debug_print(debug, f"[select_block] Found {len(matching_blocks)} blocks with matching src.")
        if not matching_blocks:
            debug_print(debug,
                        f"[select_block] No explicit translate blocks found for src '{src_filter}'. Using empty mapping.")
            return {'src': src_filter, 'default': 'unknown', 'mapping': {}}
        return combine_blocks(matching_blocks, src_filter, debug)


def get_translation(field, mapping, cond_rules, debug=False):
    """
    Returns a tuple (translation, marker, explicit) for the given field.
    Only returns an exact match from the explicit mapping.
    If no exact match is found, applies conditional rules.
    Otherwise, returns the default.
    """
    field_lower = field.lower()
    # Check for an exact match.
    if field_lower in mapping:
        return mapping[field_lower], " (explicit exact)", True
    # Check conditional rules.
    translation_from_rule = apply_conditional_rules(field_lower, cond_rules, debug)
    if translation_from_rule is not None:
        return translation_from_rule, " (conditional)", True
    # Return default.
    return "unknown", " (default)", False


def process_fields(block, cond_rules, fields_file, debug=False, only_unknown=False, fieldnames_only=False,
                   diff_unknown=False, only_default_unknown=False):
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
        translation, marker, explicit = get_translation(field, block['mapping'], cond_rules, debug)
        debug_print(debug,
                    f"[process_fields] Field='{field}' => Translation='{translation}' {marker} (explicit: {explicit})")
        if only_unknown:
            if translation == "unknown":
                if only_default_unknown and explicit:
                    continue
                if fieldnames_only:
                    print(field + (marker if diff_unknown else ""))
                else:
                    print(f"{field} -> {translation}{(marker if diff_unknown else '')}")
                found_any = True
        else:
            if fieldnames_only:
                print(field)
            else:
                print(f"{field} -> {translation}{(marker if diff_unknown and translation == 'unknown' else '')}")
            found_any = True
    if not found_any:
        if only_unknown:
            print("[process_fields] No fields produced 'unknown' (with given filtering).")
        else:
            print("[process_fields] No fields with a mapping (non-unknown) were found.")


def test_field(block, cond_rules, test_field, debug=False, fieldnames_only=False, diff_unknown=False,
               only_default_unknown=False):
    debug_print(debug, f"[test_field] Testing single field='{test_field}'")
    translation, marker, explicit = get_translation(test_field, block['mapping'], cond_rules, debug)
    if only_default_unknown and explicit:
        return
    if fieldnames_only:
        print(test_field + (marker if diff_unknown and translation == "unknown" else ""))
    else:
        print(
            f"Test field: {test_field} -> {translation}{(marker if diff_unknown and translation == 'unknown' else '')}")
    if translation == "unknown":
        debug_print(debug, "[test_field] This field is either explicitly mapped to 'unknown' or not found.")


def main():
    print("[main] Starting TranslateEvents.py ...")
    parser = argparse.ArgumentParser(description="Translate event codes using a configuration file.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--fields-file", help="File containing fields to translate (one per line)")
    group.add_argument("--test-field", help="Test a single field")
    parser.add_argument("config_file", help="Path to configuration file")
    parser.add_argument("--src-filter",
                        help="Filter for the translate block's src field (use 'ALL' to combine all blocks)",
                        default="raw_event_data.eventType")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--only-unknown", action="store_true", help="Print only fields that produce 'unknown'")
    parser.add_argument("--fieldnames-only", action="store_true",
                        help="Print only the field names (without translations)")
    parser.add_argument("--diff-unknown", action="store_true",
                        help="Differentiate unknown fields with markers: (explicit)/(conditional) vs (default)")
    parser.add_argument("--only-default-unknown", action="store_true",
                        help="Print only fields that produce 'unknown' due to default (not explicitly mapped)")
    parser.add_argument("--print-all-mappings", action="store_true",
                        help="Print all explicit mappings and conditional rules (and exit)")
    args = parser.parse_args()

    print(
        f"[main] Arguments: config_file={args.config_file}, fields_file={args.fields_file}, test_field={args.test_field}, src_filter={args.src_filter}, debug={args.debug}, only_unknown={args.only_unknown}, fieldnames_only={args.fieldnames_only}, diff_unknown={args.diff_unknown}, only_default_unknown={args.only_default_unknown}, print_all_mappings={args.print_all_mappings}")

    blocks = parse_translate_blocks(args.config_file, args.debug)

    # If src-filter is "ALL", combine all blocks.
    if norm_str(args.src_filter) == "all":
        selected_block = combine_blocks(blocks, args.src_filter, args.debug)
        cond_rules = parse_conditional_rules(args.config_file, "", args.debug)
    else:
        selected_block = select_block(blocks, args.src_filter, args.debug)
        cond_rules = parse_conditional_rules(args.config_file, args.src_filter, args.debug)

    if args.print_all_mappings:
        print_all_mappings([selected_block], cond_rules, args.diff_unknown)
        sys.exit(0)

    if args.test_field:
        test_field(selected_block, cond_rules, args.test_field, args.debug, args.fieldnames_only, args.diff_unknown,
                   args.only_default_unknown)
    elif args.fields_file:
        process_fields(selected_block, cond_rules, args.fields_file, args.debug, args.only_unknown,
                       args.fieldnames_only, args.diff_unknown, args.only_default_unknown)


if __name__ == '__main__':
    main()
