#!/usr/bin/env python3
import sys
import re

###############################################################################
#                           DSL INSTRUCTION CLASSES
###############################################################################

class DSLInstruction:
    """Base class for any DSL instruction."""
    def apply(self, data: dict) -> None:
        """
        Apply this instruction to the data in-place.
        """
        pass

class Condition:
    """
    Represents something like:
        ('raw_event_data.eventType' starts_with 'access')
        ('raw_event_data.debugContext.debugData.behaviors' exists)
    We'll store:
        field: str   (e.g. "raw_event_data.eventType")
        op: str      (e.g. "starts_with", "exists", "==", etc.)
        value: str   (e.g. "access")
    """
    def __init__(self, field: str, op: str, value: str = None):
        self.field = field
        self.op = op
        self.value = value

    def evaluate(self, data: dict) -> bool:
        # For a real DSL, you'd parse nested keys. This naive version
        # just looks at data[self.field] on the top level.
        current_val = data.get(self.field)

        if self.op == "exists":
            return current_val is not None
        elif self.op == "not exists":
            return current_val is None
        elif self.op == "starts_with":
            return isinstance(current_val, str) and current_val.startswith(self.value)
        elif self.op == "contains":
            return isinstance(current_val, str) and (self.value in current_val)
        elif self.op == "not contains":
            return isinstance(current_val, str) and (self.value not in current_val)
        elif self.op == "==":
            return current_val == self.value
        elif self.op == "!=":
            return current_val != self.value
        # ... Add more operators as needed
        return False

class IfInstruction(DSLInstruction):
    """
    if ('raw_event_data.eventType' starts_with 'access') {
        rename { ... }
        translate { ... }
        ...
    }
    """
    def __init__(self, condition: Condition, sub_instructions: list):
        self.condition = condition
        self.sub_instructions = sub_instructions

    def apply(self, data: dict) -> None:
        if self.condition.evaluate(data):
            for instr in self.sub_instructions:
                instr.apply(data)

class RenameInstruction(DSLInstruction):
    """
    rename {
      src = 'some.field'
      dest = 'some.other.field'
    }
    """
    def __init__(self, src: str, dest: str):
        self.src = src
        self.dest = dest

    def apply(self, data: dict) -> None:
        # Naive approach: rename top-level keys only
        if self.src in data:
            data[self.dest] = data[self.src]
            del data[self.src]

class TranslateInstruction(DSLInstruction):
    """
    translate {
      src = 'raw_event_data.eventType'
      dest = 'event.action'
      default = 'unknown'
      map = {
        'access.request.create' = 'download_resource'
        ...
      }
    }
    """
    def __init__(self, src: str, dest: str, default: str, mapping: dict):
        self.src = src
        self.dest = dest
        self.default = default
        self.mapping = mapping

    def apply(self, data: dict) -> None:
        value = data.get(self.src)
        if value is None:
            data[self.dest] = self.default
        else:
            data[self.dest] = self.mapping.get(value, self.default)

class SetInstruction(DSLInstruction):
    """
    set {
      dest = 'resource.type'
      value = 'credential'
    }
    """
    def __init__(self, dest: str, value: str):
        self.dest = dest
        self.value = value

    def apply(self, data: dict) -> None:
        data[self.dest] = self.value

class CopyInstruction(DSLInstruction):
    """
    copy {
      src = 'some.src'
      dest = 'some.dest'
      append = true/false (optional)
    }
    """
    def __init__(self, src: str, dest: str, append: bool = False):
        self.src = src
        self.dest = dest
        self.append = append

    def apply(self, data: dict) -> None:
        if self.src in data:
            val = data[self.src]
            if self.append:
                # If we want to append to an existing list, etc.
                if self.dest not in data:
                    data[self.dest] = []
                if isinstance(data[self.dest], list):
                    data[self.dest].append(val)
                else:
                    # fallback: overwrite
                    data[self.dest] = val
            else:
                data[self.dest] = val

###############################################################################
#                         PARSING THE DSL (NAIVE EXAMPLE)
###############################################################################

def parse_dsl(conf_file_path: str) -> list:
    """
    Parse the entire .conf file into a list of DSLInstruction objects.
    This is a naive multi-line parser that:
      1. Splits the file into "blocks" or lines
      2. For each block, tries to see if it's an 'if' block or an instruction
         like rename, translate, set, copy, etc.
      3. Returns a list of instructions that can be applied in sequence.
    """
    with open(conf_file_path, "r") as f:
        lines = f.readlines()

    # 1) Convert lines into "blocks" (like we do for 'if (...) { ... }' or
    #    single instructions 'rename { ... }' which might span multiple lines).
    blocks = _gather_blocks(lines)

    # 2) Parse each block into a DSLInstruction object
    instructions = []
    for blk in blocks:
        instr = _parse_block(blk)
        if instr:
            if isinstance(instr, list):
                # in case _parse_block returns multiple instructions
                instructions.extend(instr)
            else:
                instructions.append(instr)

    return instructions

def _gather_blocks(lines: list) -> list:
    """
    Splits the file lines into top-level blocks.
    For example:
      if ('foo' starts_with 'bar') {
        rename { ... }
        translate { ... }
      }
    becomes one block of multiple lines.
    A single line like:
      rename { src = 'x', dest = 'y' }
    is also one block.

    We do a simple brace matching approach for "if" or instructions
    that have curly braces.
    """
    blocks = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].rstrip()
        if not line or line.strip().startswith("#"):
            # Skip empty lines or comments
            i += 1
            continue

        # Check if this line starts with something like "if (" or "rename {"
        if re.match(r"^\s*(if\s*\()|(\w+\s*\{)", line):
            # We have a multi-line block potentially
            block_lines = []
            brace_count = 0
            # We'll keep track if we found the first '{'
            found_open_brace = False

            while i < n:
                block_lines.append(lines[i])
                # Count braces
                open_count = lines[i].count("{")
                close_count = lines[i].count("}")
                brace_count += (open_count - close_count)

                if open_count > 0:
                    found_open_brace = True

                i += 1

                # If we've found the matching closing brace(s) for the first open
                # and we've found at least one '{', we can break
                if found_open_brace and brace_count <= 0:
                    break

            blocks.append("".join(block_lines))
        else:
            # Single-line instruction with no braces? Or partial.
            # We'll just store it as a single block.
            blocks.append(line)
            i += 1

    return blocks

def _parse_block(block_text: str):
    """
    Given a chunk of text (could be multi-line), decide what instruction it is:
      - if (...) { ... }
      - rename { ... }
      - translate { ... }
      - set { ... }
      - copy { ... }
      - etc.
    and return the appropriate DSLInstruction object (or list of them).
    """
    # Trim leading/trailing whitespace
    blk = block_text.strip()

    # 1) Check if it's an "if" block
    if blk.startswith("if ("):
        return _parse_if_block(blk)

    # 2) Otherwise, check if it's rename, translate, set, copy
    if blk.startswith("rename {"):
        return _parse_rename_block(blk)
    if blk.startswith("translate {"):
        return _parse_translate_block(blk)
    if blk.startswith("set {"):
        return _parse_set_block(blk)
    if blk.startswith("copy {"):
        return _parse_copy_block(blk)

    # else: unrecognized
    # You'd add more instructions here (append, regex_capture, etc.)
    return None

###############################################################################
#                          PARSER HELPERS
###############################################################################

def _parse_if_block(block_text: str) -> IfInstruction:
    """
    if ('field' op 'value') {
      <sub-instructions>
    }
    or
    if ('field' exists) {
      ...
    }
    """
    lines = block_text.splitlines()
    first_line = lines[0].strip()

    # e.g.: if ('raw_event_data.eventType' starts_with 'access') {
    # Try a few patterns
    m = re.match(r"if\s*\(\s*'([^']+)'\s+(\w+)\s+'([^']+)'\s*\)\s*\{", first_line)
    if m:
        field, op, val = m.groups()
        condition = Condition(field, op, val)
    else:
        # Maybe if ('field' exists)
        m2 = re.match(r"if\s*\(\s*'([^']+)'\s+exists\s*\)\s*\{", first_line)
        if m2:
            field = m2.group(1)
            condition = Condition(field, "exists")
        else:
            # maybe if ('field' not exists)
            m3 = re.match(r"if\s*\(\s*'([^']+)'\s+not\s+exists\s*\)\s*\{", first_line)
            if m3:
                field = m3.group(1)
                condition = Condition(field, "not exists")
            else:
                # fallback: always false
                condition = Condition("", "==", None)

    # Gather sub-instructions
    sub_lines = []
    brace_count = 0
    found_open_brace = False
    # We'll skip the first line (already processed) and parse until final "}"
    # We know there's at least one '{' from gather_blocks
    i = 1
    while i < len(lines):
        line = lines[i]
        sub_lines.append(line)
        open_count = line.count("{")
        close_count = line.count("}")
        brace_count += (open_count - close_count)
        if open_count > 0:
            found_open_brace = True
        i += 1
        if found_open_brace and brace_count < 0:
            # we've closed the block
            break

    # sub_block_text is the lines inside the if-block
    sub_block_text = "\n".join(sub_lines)
    # Now we parse those sub-lines into instructions
    sub_instructions = _parse_sub_instructions(sub_block_text)
    return IfInstruction(condition, sub_instructions)

def _parse_sub_instructions(block_text: str) -> list:
    """
    Parse multiple instructions inside an if-block.
    We'll reuse _gather_blocks on these lines, then parse each block.
    """
    lines = block_text.splitlines()
    blocks = _gather_blocks(lines)
    sub_instructions = []
    for blk in blocks:
        instr = _parse_block(blk)
        if instr:
            if isinstance(instr, list):
                sub_instructions.extend(instr)
            else:
                sub_instructions.append(instr)
    return sub_instructions

def _parse_rename_block(block_text: str) -> RenameInstruction:
    """
    rename {
      src = 'foo'
      dest = 'bar'
    }
    """
    # Extract the content between the braces
    inner = _extract_braces_content(block_text)
    # Find lines like src = '...', dest = '...'
    src, dest = None, None
    pairs = re.findall(r"(\w+)\s*=\s*'([^']+)'", inner)
    for k, v in pairs:
        if k == "src":
            src = v
        elif k == "dest":
            dest = v
    return RenameInstruction(src, dest)

def _parse_translate_block(block_text: str) -> TranslateInstruction:
    """
    translate {
      src = 'raw_event_data.eventType'
      dest = 'event.action'
      default = 'unknown'
      map = {
        'foo' = 'bar'
        ...
      }
    }
    """
    inner = _extract_braces_content(block_text)

    # parse src, dest, default
    pairs = re.findall(r"(\w+)\s*=\s*'([^']+)'", inner)
    src = None
    dest = None
    default = "unknown"
    for k, v in pairs:
        if k == "src":
            src = v
        elif k == "dest":
            dest = v
        elif k == "default":
            default = v

    # parse map
    map_pattern = re.search(r"map\s*=\s*\{([^}]*)\}", inner, re.DOTALL)
    mapping = {}
    if map_pattern:
        map_content = map_pattern.group(1)
        entries = re.findall(r"'([^']+)'\s*=\s*'([^']+)'", map_content)
        for key, val in entries:
            mapping[key] = val

    return TranslateInstruction(src, dest, default, mapping)

def _parse_set_block(block_text: str) -> SetInstruction:
    """
    set {
      dest = 'resource.type'
      value = 'credential'
    }
    """
    inner = _extract_braces_content(block_text)
    dest = None
    value = None
    pairs = re.findall(r"(\w+)\s*=\s*'([^']+)'", inner)
    for k, v in pairs:
        if k == "dest":
            dest = v
        elif k == "value":
            value = v
    return SetInstruction(dest, value)

def _parse_copy_block(block_text: str) -> CopyInstruction:
    """
    copy {
      src = 'some.src'
      dest = 'some.dest'
      append = true
    }
    """
    inner = _extract_braces_content(block_text)
    src = None
    dest = None
    append = False
    # For booleans, we do a naive check
    # e.g. append = true or append = false
    # We'll first handle the string pairs
    pairs = re.findall(r"(\w+)\s*=\s*'([^']+)'", inner)
    for k, v in pairs:
        if k == "src":
            src = v
        elif k == "dest":
            dest = v

    # Now check for append = true or false (no quotes)
    m = re.search(r"append\s*=\s*(true|false)", inner)
    if m:
        append_str = m.group(1)
        append = (append_str == "true")

    return CopyInstruction(src, dest, append)

def _extract_braces_content(block_text: str) -> str:
    """
    Utility to find the content between the first '{' and the matching '}' from
    the end. Naive approach.
    """
    start_brace = block_text.find("{")
    end_brace = block_text.rfind("}")
    if start_brace == -1 or end_brace == -1 or end_brace <= start_brace:
        return ""
    return block_text[start_brace+1 : end_brace].strip()

###############################################################################
#                          APPLYING THE DSL TO EVENTS
###############################################################################

def apply_instructions(data: dict, instructions: list) -> dict:
    """
    Apply each DSLInstruction in sequence to the data dictionary.
    Returns the modified data.
    """
    for instr in instructions:
        instr.apply(data)
    return data

###############################################################################
#                                MAIN SCRIPT
###############################################################################

def main():
    if len(sys.argv) != 3:
        print("Usage: python dsl_wrapper.py <parser.conf> <event_types.txt>")
        sys.exit(1)

    conf_file = sys.argv[1]
    event_types_file = sys.argv[2]

    # 1) Parse DSL instructions from the .conf file
    instructions = parse_dsl(conf_file)

    # 2) Read event types from the text file
    try:
        with open(event_types_file, "r") as f:
            event_types = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: file '{event_types_file}' not found.")
        sys.exit(1)

    # 3) For each event type, build a minimal data dict and apply instructions
    unknown_events = []
    for evt in event_types:
        # Minimal dictionary so "raw_event_data.eventType" can be found:
        data = {
            "raw_event_data.eventType": evt
        }
        apply_instructions(data, instructions)

        # Check the result
        event_action = data.get("event.action", "unknown")
        if event_action == "unknown":
            unknown_events.append(evt)

    # 4) Print out which events are "unknown"
    print("Event types producing an 'unknown' event_action:")
    for ue in unknown_events:
        print(ue)

if __name__ == "__main__":
    main()
