import re


###############################################################################
# DATA STRUCTURES: We define some classes to hold DSL instructions.
###############################################################################

class DSLInstruction:
    """Base class for any DSL instruction."""

    def apply(self, data: dict) -> None:
        """Apply this instruction to the 'data' dictionary in-place."""
        pass


class IfInstruction(DSLInstruction):
    """
    Represents a block like:
       if ('raw_event_data.eventType' starts_with 'access') {
         ...sub-instructions...
       }
    We store:
      - condition: a Condition object describing how to evaluate 'starts_with' / 'exists' / etc.
      - sub_instructions: a list of DSLInstruction objects to apply if condition is true.
    """

    def __init__(self, condition, sub_instructions):
        self.condition = condition
        self.sub_instructions = sub_instructions

    def apply(self, data: dict) -> None:
        if self.condition.evaluate(data):
            for instr in self.sub_instructions:
                instr.apply(data)


class RenameInstruction(DSLInstruction):
    """
    rename { src = 'some.source.path', dest = 'some.dest.path' }
    We'll just store the src/dest and do a naive rename in apply().
    """

    def __init__(self, src, dest):
        self.src = src
        self.dest = dest

    def apply(self, data: dict) -> None:
        # naive: if 'some.source.path' is in data, rename it to 'some.dest.path'
        # In real usage, you might want to handle nested dict paths, e.g. "raw_event_data.eventType".
        # Here we do a simple top-level check.
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

    def __init__(self, src, dest, default, mapping):
        self.src = src
        self.dest = dest
        self.default = default
        self.mapping = mapping

    def apply(self, data: dict) -> None:
        # Again, naive approach: look up data[src], see if it's in mapping.
        # If not, set data[dest] = default.
        value = data.get(self.src)
        if value is None:
            data[self.dest] = self.default
        else:
            data[self.dest] = self.mapping.get(value, self.default)


###############################################################################
# CONDITIONS: We define a small class to handle "starts_with", "exists", etc.
###############################################################################

class Condition:
    """
    Example: ('raw_event_data.eventType' starts_with 'access')
    or:      ('raw_event_data.debugContext.debugData.behaviors' exists)
    We'll store something like:
      field = 'raw_event_data.eventType'
      op = 'starts_with'
      value = 'access'
    or
      field = 'raw_event_data.debugContext.debugData.behaviors'
      op = 'exists'
      value = None
    """

    def __init__(self, field: str, op: str, value: str = None):
        self.field = field
        self.op = op
        self.value = value

    def evaluate(self, data: dict) -> bool:
        # Very naive approach: just check data[field] at top level
        # Real DSL suggests nested fields, so you'd need a function
        # to dig into data via dot notation. We skip that for brevity.
        current_val = data.get(self.field)
        if self.op == 'exists':
            return current_val is not None
        elif self.op == 'starts_with':
            if not isinstance(current_val, str):
                return False
            return current_val.startswith(self.value)
        elif self.op == 'contains':
            if not isinstance(current_val, str):
                return False
            return self.value in current_val
        elif self.op == '==':
            return current_val == self.value
        elif self.op == '!=':
            return current_val != self.value
        # etc.
        return False


###############################################################################
# PARSER: read lines from the DSL file and produce a list of DSLInstruction.
#         This is a *very simplified* example that only handles a few patterns.
###############################################################################

def parse_dsl(conf_file_path: str):
    """
    Reads the DSL lines from the .conf file, and returns a list of DSLInstruction objects.
    This parser is incomplete and only demonstrates a small subset:
      - if (...) { ... } blocks
      - rename { ... }
      - translate { ... }
    Expand it as needed for your DSL (copy, set, regex_capture, etc.).
    """
    instructions = []
    with open(conf_file_path, 'r') as f:
        lines = f.readlines()

    # We'll do a two-pass approach:
    # 1) Flatten out "if { ... }" blocks.
    # 2) Parse each line or block into an instruction object.
    # This is minimal; real DSL parsing might require a proper parser library.

    # Step 1: gather blocks
    # We detect lines starting with "if (" and read until matching "}".
    i = 0
    n = len(lines)
    blocks = []
    while i < n:
        line = lines[i].strip()
        if line.startswith("#") or not line:
            # comment or blank
            i += 1
            continue

        if line.startswith("if ("):
            # gather block
            block_lines = [line]
            i += 1
            brace_count = line.count("{") - line.count("}")
            while i < n and brace_count > 0:
                line2 = lines[i]
                block_lines.append(line2)
                # keep track of braces
                brace_count += line2.count("{")
                brace_count -= line2.count("}")
                i += 1
            block_text = "\n".join(block_lines)
            blocks.append(block_text)
        else:
            # single-line instruction or something else
            blocks.append(line)
            i += 1

    # Step 2: parse each block or line
    parsed_instructions = []
    for blk in blocks:
        blk = blk.strip()
        if blk.startswith("if ("):
            parsed_instructions.append(_parse_if_block(blk))
        elif blk.startswith("rename {"):
            parsed_instructions.append(_parse_rename(blk))
        elif blk.startswith("translate {"):
            parsed_instructions.append(_parse_translate(blk))
        else:
            # We ignore everything else in this minimal example
            # You could add elif for copy, set, etc.
            pass

    # Flatten top-level instructions
    # (IfInstruction may contain sub-instructions inside.)
    instructions.extend(parsed_instructions)
    return instructions


###############################################################################
# HELPER PARSER FUNCTIONS (extremely naive)
###############################################################################

def _parse_if_block(block_text: str) -> IfInstruction:
    """
    Example block_text:
    if ('raw_event_data.eventType' starts_with 'access') {
      rename { src = 'foo', dest = 'bar' }
      translate { src = 'some_src', ... }
    }
    We'll parse out the condition, then parse sub-lines for instructions.
    """
    # 1) parse condition line from the first line
    lines = block_text.splitlines()
    first_line = lines[0].strip()
    # if ('raw_event_data.eventType' starts_with 'access') {
    # We'll do a naive regex to extract the inside of if (...)
    m = re.match(r"if\s*\(\s*'([^']+)'\s+(\w+)\s+'([^']+)'\s*\)\s*\{", first_line)
    if not m:
        # Maybe it's an if with 'exists' or something else.
        # We'll do another pattern check for "if ('something' exists)"
        m2 = re.match(r"if\s*\(\s*'([^']+)'\s+exists\s*\)\s*\{", first_line)
        if m2:
            field = m2.group(1)
            op = 'exists'
            value = None
            condition = Condition(field, op, value)
        else:
            # fallback: unrecognized
            # Return an IfInstruction with a "never true" condition
            condition = Condition("", "==", None)
    else:
        field = m.group(1)
        op = m.group(2)  # e.g. "starts_with"
        value = m.group(3)
        condition = Condition(field, op, value)

    # 2) parse sub-instructions (everything until the final "}")
    sub_instructions = []
    # gather lines from lines[1:-1] ignoring the final "}"
    sub_block_lines = []
    brace_count = 1
    for sub_line in lines[1:]:
        if "}" in sub_line:
            brace_count -= sub_line.count("}")
            if brace_count <= 0:
                break
        sub_block_lines.append(sub_line)

    # parse those lines similarly (recursively or just line by line)
    # For brevity, we do line by line, ignoring nested if's in this example.
    for sub_line in sub_block_lines:
        sl = sub_line.strip()
        if sl.startswith("rename {"):
            sub_instructions.append(_parse_rename(sl))
        elif sl.startswith("translate {"):
            sub_instructions.append(_parse_translate(sl))
        # else: ignore other instructions in this minimal example

    return IfInstruction(condition, sub_instructions)


def _parse_rename(line: str) -> RenameInstruction:
    """
    rename { src = 'raw_event_data.event_type', dest = 'raw_event_data.eventType'}
    We'll do a naive regex to extract src/dest.
    """
    # naive approach
    # 1) get inside of rename { ... }
    inner = line[line.index("{") + 1: line.rindex("}")]
    # e.g. " src = 'raw_event_data.event_type', dest = 'raw_event_data.eventType'"
    # 2) parse out src/dest
    # We'll do a simple findall
    pairs = re.findall(r"(\w+)\s*=\s*'([^']+)'", inner)
    # pairs might be [('src','raw_event_data.event_type'), ('dest','raw_event_data.eventType')]
    src = None
    dest = None
    for key, val in pairs:
        if key == 'src':
            src = val
        elif key == 'dest':
            dest = val
    return RenameInstruction(src, dest)


def _parse_translate(line: str) -> TranslateInstruction:
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
    We'll parse src, dest, default, and the map entries.
    """
    # Step 1: isolate the block inside "translate { ... }"
    inner = line[line.index("{") + 1: line.rindex("}")]
    # This might be multiple lines if it's a block. For simplicity, handle single-line usage
    # or assume the user put it all on one line. If multiline, you'd do something similar
    # to the if-block approach. This is just a minimal example.

    # parse src, dest, default
    # We'll do a naive approach with findall again:
    pairs = re.findall(r"(\w+)\s*=\s*'([^']+)'", inner)
    src = None
    dest = None
    default = "unknown"
    for k, v in pairs:
        if k == 'src':
            src = v
        elif k == 'dest':
            dest = v
        elif k == 'default':
            default = v

    # parse map
    # We'll look for: map = { 'key' = 'value' 'key2' = 'value2' ... }
    m = re.search(r"map\s*=\s*\{([^}]*)\}", inner, re.DOTALL)
    mapping = {}
    if m:
        map_content = m.group(1)
        # find all pairs 'key' = 'value'
        entries = re.findall(r"'([^']+)'\s*=\s*'([^']+)'", map_content)
        for k, v in entries:
            mapping[k] = v

    return TranslateInstruction(src, dest, default, mapping)
