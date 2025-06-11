#!/usr/bin/env python3
import sys
import re
from lark import Lark, Transformer, v_args

###############################################################################
#                           DSL GRAMMAR
###############################################################################
# This grammar handles the statements used in your okta.conf file:
#
# - Statements: copy, set, date, rename, parse_ip, append, regex_capture,
#   to_lower, from_json, translate, del, and foreach.
#
# - if (...) { ... } with conditions (==, !=, starts_with, contains, etc.)
# - foreach 'item' in 'some.path' { ... }
# - translate { src=..., dest=..., map={...}, default=... }
# - Compound conditions using "or" and "and"
#
# Parameter lists in copy, set, rename, date, parse_ip, append, and regex_capture
# allow parameters to be separated by an optional comma.
###############################################################################

dsl_grammar = r"""
start: statement*

statement: if_statement
         | foreach_stmt
         | rename_stmt
         | copy_stmt
         | set_stmt
         | date_stmt
         | parse_ip_stmt
         | append_stmt
         | regex_capture_stmt
         | to_lower_stmt
         | from_json_stmt
         | translate_stmt
         | del_stmt
         | COMMENT
         | _blank_line

// -------- IF BLOCK -----------
if_statement: "if" "(" cond_expr ")" "{" statement* "}"
?cond_expr: cond_expr "or" cond_term   -> or_expr
          | cond_expr "and" cond_term  -> and_expr
          | cond_term
?cond_term: bin_condition
          | exists_condition
          | not_exists_condition
          | "(" cond_expr ")"
bin_condition: quoted_field condition_op value_expr -> bin_condition
exists_condition: quoted_field "exists"             -> exists_condition
not_exists_condition: quoted_field "not" "exists"     -> not_exists_condition
condition_op: "==" | "!="
            | "starts_with" | "not_starts_with"
            | "contains" | "not_contains"
            | not_contains_op
not_contains_op: "not" "contains"
?value_expr: quoted_field
           | bool_value

// -------- FOREACH -----------
foreach_stmt: "foreach" SSTRING "in" quoted_field "{" statement* "}"

// -------- COPY -----------
copy_stmt: "copy" "{" copy_param_list? "}"
copy_param_list: copy_param (COMMA? copy_param)*
?copy_param: named_copy_param
           | bare_copy_param
named_copy_param: ("src" | "dest" | "append") "=" (quoted_field | bool_value)
bare_copy_param: quoted_field -> copy_bare_string

// -------- SET -----------
set_stmt: "set" "{" set_param_list? "}"
set_param_list: set_param (COMMA? set_param)*
set_param: ("dest" | "value") "=" quoted_field

// -------- RENAME -----------
rename_stmt: "rename" "{" rename_param_list? "}"
rename_param_list: rename_param (COMMA? rename_param)*
rename_param: ("src" | "dest") "=" quoted_field

// -------- DATE -----------
date_stmt: "date" "{" date_param_list? "}"
date_param_list: date_param (COMMA? date_param)*
date_param: "src" "=" quoted_field

// -------- PARSE_IP -----------
parse_ip_stmt: "parse_ip" "{" parse_ip_param_list? "}"
parse_ip_param_list: parse_ip_param (COMMA? parse_ip_param)*
parse_ip_param: ("src" | "dest") "=" quoted_field

// -------- APPEND -----------
append_stmt: "append" "{" append_param_list? "}"
append_param_list: append_param (COMMA? append_param)*
append_param: ("dest" | "value") "=" quoted_field

// -------- REGEX_CAPTURE -----------
regex_capture_stmt: "regex_capture" "{" regex_capture_param_list? "}"
regex_capture_param_list: regex_capture_param (COMMA? regex_capture_param)*
regex_capture_param: ("src" | "dest" | "regex") "=" quoted_field

// -------- TO_LOWER -----------
to_lower_stmt: "to_lower" "{" "src" "=" quoted_field "}"
// -------- FROM_JSON -----------
from_json_stmt: "from_json" "{" "src" "=" quoted_field "}"
// -------- TRANSLATE -----------
translate_stmt: "translate" "{" translate_item+ "}"
?translate_item: translate_param
                | map_block
translate_param: ("src" | "dest" | "default") "=" quoted_field
map_block: "map" "=" "{" map_entry* "}"
map_entry: quoted_field "=" quoted_field

// -------- DEL -----------
del_stmt: "del" "{" "src" "=" quoted_field "}"

bool_value: "true" | "false"

COMMENT: /[ \t]*#.*/ 
_blank_line: /[ \t]*[\r\n]+/
COMMA: ","
SSTRING: SINGLE_QUOTED_STRING
quoted_field: SINGLE_QUOTED_STRING
quoted_regex: SINGLE_QUOTED_STRING

// SINGLE_QUOTED_STRING accepts escaped characters.
SINGLE_QUOTED_STRING: "'" ( /\\./ | /[^'\\]/ )* "'"

%import common.WS
%ignore WS
"""

###############################################################################
#               INSTRUCTION CLASSES & NESTED-KEY HELPERS
###############################################################################
class DSLInstruction:
    def apply(self, data: dict) -> None:
        pass

def get_nested(data: dict, path: str):
    if not path:
        return None
    keys = path.split(".")
    cur = data
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur

def set_nested(data: dict, path: str, value):
    if not path:
        return
    keys = path.split(".")
    cur = data
    for k in keys[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    cur[keys[-1]] = value

def delete_nested(data: dict, path: str):
    if not path:
        return
    keys = path.split(".")
    cur = data
    for k in keys[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            return
        cur = cur[k]
    if keys[-1] in cur:
        del cur[keys[-1]]

###############################################################################
#                     IF CONDITIONS
###############################################################################
class Condition:
    def evaluate(self, data: dict) -> bool:
        return False

class BinaryCondition(Condition):
    def __init__(self, field, op, value):
        self.field = field
        self.op = op
        self.value = value
    def evaluate(self, data: dict) -> bool:
        lhs = get_nested(data, self.field)
        if self.value in ("true", "false"):
            rhs_bool = (self.value == "true")
            lhs_bool = bool(lhs)
            if self.op == "==":
                return lhs_bool == rhs_bool
            elif self.op == "!=":
                return lhs_bool != rhs_bool
            return False
        if not isinstance(lhs, str):
            lhs = str(lhs) if lhs is not None else ""
        if self.op == "==":
            return lhs == self.value
        elif self.op == "!=":
            return lhs != self.value
        elif self.op == "starts_with":
            return lhs.startswith(self.value)
        elif self.op == "not_starts_with":
            return not lhs.startswith(self.value)
        elif self.op == "contains":
            return self.value in lhs
        elif self.op == "not_contains":
            return self.value not in lhs
        return False

class ExistsCondition(Condition):
    def __init__(self, field):
        self.field = field
    def evaluate(self, data: dict) -> bool:
        return get_nested(data, self.field) is not None

class NotExistsCondition(Condition):
    def __init__(self, field):
        self.field = field
    def evaluate(self, data: dict) -> bool:
        return get_nested(data, self.field) is None

class OrCondition(Condition):
    def __init__(self, left, right):
        self.left = left
        self.right = right
    def evaluate(self, data: dict) -> bool:
        return self.left.evaluate(data) or self.right.evaluate(data)

class AndCondition(Condition):
    def __init__(self, left, right):
        self.left = left
        self.right = right
    def evaluate(self, data: dict) -> bool:
        return self.left.evaluate(data) and self.right.evaluate(data)

###############################################################################
#                  DSL INSTRUCTIONS
###############################################################################
class IfInstruction(DSLInstruction):
    def __init__(self, condition: Condition, sub_instructions: list):
        self.condition = condition
        self.sub_instructions = sub_instructions
    def apply(self, data: dict) -> None:
        if self.condition.evaluate(data):
            for instr in self.sub_instructions:
                instr.apply(data)

class ForeachInstruction(DSLInstruction):
    def __init__(self, loop_var, array_path, sub_instructions):
        self.loop_var = loop_var
        self.array_path = array_path
        self.sub_instructions = sub_instructions
    def apply(self, data: dict) -> None:
        arr = get_nested(data, self.array_path)
        if not isinstance(arr, list):
            return
        for element in arr:
            old_val = data.get(self.loop_var)
            data[self.loop_var] = element
            for instr in self.sub_instructions:
                instr.apply(data)
            if old_val is None:
                del data[self.loop_var]
            else:
                data[self.loop_var] = old_val

class RenameInstruction(DSLInstruction):
    def __init__(self, src, dest):
        self.src = src
        self.dest = dest
    def apply(self, data: dict) -> None:
        val = get_nested(data, self.src)
        if val is not None:
            set_nested(data, self.dest, val)
            delete_nested(data, self.src)

class CopyInstruction(DSLInstruction):
    def __init__(self, src, dest, append=False):
        self.src = src
        self.dest = dest
        self.append = append
    def apply(self, data: dict) -> None:
        val = get_nested(data, self.src)
        if val is not None:
            if self.append:
                existing = get_nested(data, self.dest)
                if existing is None:
                    set_nested(data, self.dest, [val])
                elif isinstance(existing, list):
                    existing.append(val)
                else:
                    set_nested(data, self.dest, val)
            else:
                set_nested(data, self.dest, val)

class SetInstruction(DSLInstruction):
    def __init__(self, dest, value):
        self.dest = dest
        self.value = value
    def apply(self, data: dict) -> None:
        set_nested(data, self.dest, self.value)

class DateInstruction(DSLInstruction):
    def __init__(self, src):
        self.src = src
    def apply(self, data: dict):
        pass  # Process the date as needed

class ParseIpInstruction(DSLInstruction):
    def __init__(self, src, dest):
        self.src = src
        self.dest = dest
    def apply(self, data: dict) -> None:
        val = get_nested(data, self.src)
        if val:
            set_nested(data, self.dest, val)

class AppendInstruction(DSLInstruction):
    def __init__(self, dest, value):
        self.dest = dest
        self.value = value
    def apply(self, data: dict) -> None:
        existing = get_nested(data, self.dest)
        if existing is None:
            set_nested(data, self.dest, [self.value])
        elif isinstance(existing, list):
            existing.append(self.value)
        else:
            set_nested(data, self.dest, [existing, self.value])

class RegexCaptureInstruction(DSLInstruction):
    def __init__(self, src, dest, pattern):
        self.src = src
        self.dest = dest
        self.pattern = pattern
    def apply(self, data: dict) -> None:
        text = get_nested(data, self.src)
        if not isinstance(text, str):
            return
        m = re.search(self.pattern, text)
        if m:
            captured = m.group(1) if m.groups() else m.group(0)
            set_nested(data, self.dest, captured)

class ToLowerInstruction(DSLInstruction):
    def __init__(self, src):
        self.src = src
    def apply(self, data: dict) -> None:
        val = get_nested(data, self.src)
        if isinstance(val, str):
            set_nested(data, self.src, val.lower())

class FromJsonInstruction(DSLInstruction):
    def __init__(self, src):
        self.src = src
    def apply(self, data: dict) -> None:
        import json
        val = get_nested(data, self.src)
        if isinstance(val, str):
            try:
                parsed = json.loads(val)
                set_nested(data, self.src, parsed)
            except json.JSONDecodeError:
                pass

class DelInstruction(DSLInstruction):
    def __init__(self, src):
        self.src = src
    def apply(self, data: dict) -> None:
        delete_nested(data, self.src)

class TranslateInstruction(DSLInstruction):
    def __init__(self, src, dest, default, mapping):
        self.src = src
        self.dest = dest
        self.default = default
        self.mapping = mapping
    def apply(self, data: dict) -> None:
        value = get_nested(data, self.src)
        if value is None:
            set_nested(data, self.dest, self.default)
        else:
            set_nested(data, self.dest, self.mapping.get(value, self.default))

###############################################################################
#                          TRANSFORMER
###############################################################################
class DSLTransformer(Transformer):
    def start(self, items):
        result = []
        for i in items:
            if isinstance(i, list):
                result.extend(i)
            else:
                result.append(i)
        return result

    def statement(self, items):
        if not items:
            return []
        if isinstance(items[0], DSLInstruction):
            return [items[0]]
        return []

    @v_args(inline=True)
    def bool_value(self, val):
        return str(val)

    # IF
    def if_statement(self, items):
        cond = items[0]
        subs = items[1] if len(items) > 1 and isinstance(items[1], list) else []
        return IfInstruction(cond, subs)

    def or_expr(self, items):
        return OrCondition(items[0], items[1])

    def and_expr(self, items):
        return AndCondition(items[0], items[1])

    def bin_condition(self, items):
        field_token, op_token, value_token = items
        field = field_token[1:-1]
        op = str(op_token)
        if value_token.startswith("'"):
            val_str = value_token[1:-1]
        else:
            val_str = value_token
        return BinaryCondition(field, op, val_str)

    def condition_op(self, items):
        return str(items[0])

    def not_contains_op(self, items):
        return "not_contains"

    def exists_condition(self, items):
        field = items[0][1:-1]
        return ExistsCondition(field)

    def not_exists_condition(self, items):
        field = items[0][1:-1]
        return NotExistsCondition(field)

    # FOREACH
    def foreach_stmt(self, items):
        loop_var = items[0][1:-1]
        arr_path = items[1][1:-1]
        subs = items[2] if len(items) > 2 else []
        return ForeachInstruction(loop_var, arr_path, subs)

    # COPY
    def copy_stmt(self, items):
        if not items:
            return CopyInstruction(None, None, False)
        param_list = items[0]
        src_val = None
        dest_val = None
        app = False
        for (k, v) in param_list:
            if k == "src":
                src_val = v[1:-1]
            elif k == "dest":
                dest_val = v[1:-1]
            elif k == "append":
                app = (v == "true")
        return CopyInstruction(src_val, dest_val, app)

    def copy_param_list(self, items):
        return items

    def named_copy_param(self, items):
        if len(items) < 2:
            print("Warning: Incomplete param. items={0}. Defaulting to src='missing'".format(items))
            return ("src", "'missing'")
        return (items[0], items[1])

    def copy_bare_string(self, items):
        return ("src", items[0])

    # SET
    def set_stmt(self, items):
        if not items:
            return SetInstruction(None, None)
        param_list = items[0]
        d_val = None
        v_val = None
        for (k, v) in param_list:
            if k == "dest":
                d_val = v[1:-1]
            elif k == "value":
                v_val = v[1:-1]
        return SetInstruction(d_val, v_val)

    def set_param_list(self, items):
        return items

    def set_param(self, items):
        return (items[0], items[1])

    # DATE
    def date_stmt(self, items):
        if not items:
            return DateInstruction(None)
        param_list = items[0]
        src_val = None
        for (k, v) in param_list:
            if k == "src":
                src_val = v[1:-1]
        return DateInstruction(src_val)

    def date_param_list(self, items):
        return items

    def date_param(self, items):
        return (items[0], items[1])

    # RENAME
    def rename_stmt(self, items):
        if not items:
            return RenameInstruction(None, None)
        param_list = items[0]
        s_val = None
        d_val = None
        for (k, v) in param_list:
            if k == "src":
                s_val = v[1:-1]
            elif k == "dest":
                d_val = v[1:-1]
        return RenameInstruction(s_val, d_val)

    def rename_param_list(self, items):
        return items

    def rename_param(self, items):
        return (items[0], items[1])

    # PARSE_IP
    def parse_ip_stmt(self, items):
        if not items:
            return ParseIpInstruction(None, None)
        param_list = items[0]
        s_val = None
        d_val = None
        for (k, v) in param_list:
            if k == "src":
                s_val = v[1:-1]
            elif k == "dest":
                d_val = v[1:-1]
        return ParseIpInstruction(s_val, d_val)

    def parse_ip_param_list(self, items):
        return items

    def parse_ip_param(self, items):
        return (items[0], items[1])

    # APPEND
    def append_stmt(self, items):
        if not items:
            return AppendInstruction(None, None)
        param_list = items[0]
        d_val = None
        v_val = None
        for (k, v) in param_list:
            if k == "dest":
                d_val = v[1:-1]
            elif k == "value":
                v_val = v[1:-1]
        return AppendInstruction(d_val, v_val)

    def append_param_list(self, items):
        return items

    def append_param(self, items):
        return (items[0], items[1])

    # REGEX_CAPTURE
    def regex_capture_stmt(self, items):
        if not items:
            return RegexCaptureInstruction(None, None, None)
        param_list = items[0]
        s_val = None
        d_val = None
        r_val = None
        for (k, v) in param_list:
            if k == "src":
                s_val = v[1:-1]
            elif k == "dest":
                d_val = v[1:-1]
            elif k == "regex":
                r_val = v[1:-1]
        return RegexCaptureInstruction(s_val, d_val, r_val)

    def regex_capture_param_list(self, items):
        return items

    def regex_capture_param(self, items):
        return (items[0], items[1])

    # TO_LOWER
    def to_lower_stmt(self, items):
        param = items[0]
        return ToLowerInstruction(param[1][1:-1])

    # FROM_JSON
    def from_json_stmt(self, items):
        param = items[0]
        return FromJsonInstruction(param[1][1:-1])

    # DEL
    def del_stmt(self, items):
        param = items[0]
        return DelInstruction(param[1][1:-1])

    # TRANSLATE
    def translate_stmt(self, items):
        src = None
        dest = None
        default = "unknown"
        map_dct = {}
        for x in items:
            if isinstance(x, dict):
                map_dct = x
            elif isinstance(x, tuple):
                k, v = x
                vv = v[1:-1]
                if k == "src":
                    src = vv
                elif k == "dest":
                    dest = vv
                elif k == "default":
                    default = vv
        return TranslateInstruction(src, dest, default, map_dct)

    def translate_item(self, items):
        return items[0]

    def translate_param(self, items):
        return (items[0], items[1])

    def map_block(self, items):
        d = {}
        for (k, v) in items:
            d[k[1:-1]] = v[1:-1]
        return d

    def map_entry(self, items):
        return (items[0], items[1])

    # COMMENTS / BLANK
    def COMMENT(self, token):
        return []
    def _blank_line(self, token):
        return []

###############################################################################
#                               MAIN SCRIPT
###############################################################################
def parse_dsl_file(conf_file: str):
    parser = Lark(dsl_grammar, start='start', parser='lalr')
    with open(conf_file, 'r') as f:
        content = f.read()
    parse_tree = parser.parse(content)
    instructions = DSLTransformer().transform(parse_tree)
    flat = []
    for item in instructions:
        if isinstance(item, list):
            flat.extend(item)
        else:
            flat.append(item)
    return flat

def apply_instructions(data: dict, instructions: list):
    for instr in instructions:
        instr.apply(data)

def main():
    if len(sys.argv) != 3:
        print("Usage: python dsl_wrapper.py <parser.conf> <event_types.txt>")
        sys.exit(1)
    conf_file = sys.argv[1]
    event_types_file = sys.argv[2]
    try:
        instructions = parse_dsl_file(conf_file)
    except Exception as e:
        print(f"Error parsing DSL file '{conf_file}': {e}")
        sys.exit(1)
    try:
        with open(event_types_file, "r") as f:
            event_types = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: file '{event_types_file}' not found.")
        sys.exit(1)
    unknown_actions = []
    for evt in event_types:
        data = {"raw_event_data": {"eventType": evt}}
        apply_instructions(data, instructions)
        action = get_nested(data, "event.action")
        if action is None or action == "unknown":
            unknown_actions.append(evt)
    print("Event types producing an 'unknown' event_action:")
    for e in unknown_actions:
        print(e)

if __name__ == "__main__":
    main()
