#!/usr/bin/env python3
"""
assembler.py - Hack Assembler (Nand2Tetris, Project 6)

Author : Vansh Nibhoria (Roll No. 2501730240, K = 40)
Course : B.Tech CSE AI/ML, K.R. Mangalam University

Usage  : python assembler.py Prog.asm      ->  writes Prog.hack

Part B extra feature (K mod 3 = 1):
    Every invalid line in the .asm file is reported as
        "Line <n>: <message>"
    (n = line number in the ORIGINAL file, 1-based). All errors found are
    listed, no .hack file is produced, and the program exits with status 1
    instead of crashing with a traceback.

Design: two passes
    Pass 1 - strip comments/whitespace, record label addresses (LABEL),
             collect the instructions with their original line numbers.
    Pass 2 - translate A- and C-instructions to 16-bit binary,
             allocating new variables from RAM address 16 upward.
"""

import os
import re
import sys

# --------------------------------------------------------------------------
# Lookup tables
# --------------------------------------------------------------------------

# comp field: mnemonic -> 7 bits "a c1 c2 c3 c4 c5 c6"
COMP_TABLE = {
    "0": "0101010", "1": "0111111", "-1": "0111010",
    "D": "0001100", "A": "0110000", "!D": "0001101",
    "!A": "0110001", "-D": "0001111", "-A": "0110011",
    "D+1": "0011111", "A+1": "0110111", "D-1": "0001110",
    "A-1": "0110010", "D+A": "0000010", "D-A": "0010011",
    "A-D": "0000111", "D&A": "0000000", "D|A": "0010101",
    "M": "1110000", "!M": "1110001", "-M": "1110011",
    "M+1": "1110111", "M-1": "1110010", "D+M": "1000010",
    "D-M": "1010011", "M-D": "1000111", "D&M": "1000000",
    "D|M": "1010101",
}

DEST_TABLE = {
    "": "000", "M": "001", "D": "010", "MD": "011",
    "A": "100", "AM": "101", "AD": "110", "AMD": "111",
}

JUMP_TABLE = {
    "": "000", "JGT": "001", "JEQ": "010", "JGE": "011",
    "JLT": "100", "JNE": "101", "JLE": "110", "JMP": "111",
}

PREDEFINED_SYMBOLS = {
    "SP": 0, "LCL": 1, "ARG": 2, "THIS": 3, "THAT": 4,
    "SCREEN": 16384, "KBD": 24576,
    **{"R%d" % i: i for i in range(16)},
}

SYMBOL_RE = re.compile(r"^[A-Za-z_.$:][A-Za-z0-9_.$:]*$")
MAX_A_VALUE = 32767          # A-instructions are 15 bits wide
FIRST_VARIABLE_ADDRESS = 16


class AsmError(Exception):
    """Raised for a single invalid line; carries the line number."""

    def __init__(self, line_no, message):
        super().__init__(message)
        self.line_no = line_no
        self.message = message


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def clean_line(raw):
    """Remove comments and ALL whitespace from one source line."""
    code = raw.split("//", 1)[0]
    return "".join(code.split())


def translate_c(text, line_no):
    """Translate a C-instruction (dest=comp;jump) to 16-bit binary."""
    dest, comp, jump = "", text, ""

    if text.count("=") > 1:
        raise AsmError(line_no, "invalid instruction (more than one '=')")
    if text.count(";") > 1:
        raise AsmError(line_no, "invalid instruction (more than one ';')")

    if "=" in text:
        dest, comp = text.split("=", 1)
    if ";" in comp:
        comp, jump = comp.split(";", 1)

    if dest not in DEST_TABLE:
        raise AsmError(line_no, "invalid dest field '%s'" % dest)
    if comp not in COMP_TABLE:
        if comp == "":
            raise AsmError(line_no, "invalid instruction (missing comp field)")
        raise AsmError(line_no, "invalid comp field '%s'" % comp)
    if jump not in JUMP_TABLE:
        raise AsmError(line_no, "invalid jump field '%s'" % jump)

    return "111" + COMP_TABLE[comp] + DEST_TABLE[dest] + JUMP_TABLE[jump]


# --------------------------------------------------------------------------
# Pass 1: labels
# --------------------------------------------------------------------------

def first_pass(lines):
    """
    Returns (instructions, symbols, errors)
      instructions : list of (line_no, text) - real instructions only
      symbols      : symbol table incl. labels
      errors       : list of AsmError found while scanning
    """
    symbols = dict(PREDEFINED_SYMBOLS)
    instructions = []
    errors = []
    rom_address = 0

    for line_no, raw in enumerate(lines, start=1):
        text = clean_line(raw)
        if not text:
            continue                                  # blank / comment-only

        if text.startswith("("):                      # label declaration
            if not text.endswith(")") or len(text) < 3:
                errors.append(AsmError(line_no, "malformed label '%s'" % text))
                continue
            name = text[1:-1]
            if not SYMBOL_RE.match(name):
                errors.append(AsmError(line_no, "invalid label name '%s'" % name))
            elif name in symbols:
                errors.append(AsmError(line_no, "label '%s' is already defined" % name))
            else:
                symbols[name] = rom_address           # address of NEXT instruction
            continue                                  # labels emit no code

        instructions.append((line_no, text))
        rom_address += 1

    return instructions, symbols, errors


# --------------------------------------------------------------------------
# Pass 2: translation
# --------------------------------------------------------------------------

def translate_a(text, symbols, state, line_no):
    """Translate an A-instruction; allocates variables on first use."""
    body = text[1:]
    if body == "":
        raise AsmError(line_no, "invalid instruction ('@' with no value)")

    if body.isdigit():
        value = int(body)
        if value > MAX_A_VALUE:
            raise AsmError(line_no, "A-instruction value %d out of range (0-%d)"
                           % (value, MAX_A_VALUE))
    elif SYMBOL_RE.match(body):
        if body not in symbols:                       # new variable
            symbols[body] = state["next_var"]
            state["next_var"] += 1
        value = symbols[body]
    else:
        raise AsmError(line_no, "invalid A-instruction '%s'" % text)

    return format(value, "016b")


def second_pass(instructions, symbols):
    """Returns (binary_lines, errors)."""
    state = {"next_var": FIRST_VARIABLE_ADDRESS}
    output, errors = [], []

    for line_no, text in instructions:
        try:
            if text.startswith("@"):
                output.append(translate_a(text, symbols, state, line_no))
            else:
                output.append(translate_c(text, line_no))
        except AsmError as err:
            errors.append(err)

    return output, errors


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

def assemble(lines):
    """Assemble a list of source lines -> (binary_lines, sorted_errors)."""
    instructions, symbols, errors = first_pass(lines)
    binary, errors2 = second_pass(instructions, symbols)
    all_errors = sorted(errors + errors2, key=lambda e: e.line_no)
    return binary, all_errors


def main(argv):
    if len(argv) != 2 or not argv[1].lower().endswith(".asm"):
        print("Usage: python assembler.py <Prog.asm>", file=sys.stderr)
        return 2

    in_path = argv[1]
    out_path = os.path.splitext(in_path)[0] + ".hack"

    try:
        with open(in_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        print("Error: cannot read '%s': %s" % (in_path, exc), file=sys.stderr)
        return 1

    binary, errors = assemble(lines)

    if errors:                                        # Part B (K=40) feature
        for err in errors:
            print("Line %d: %s" % (err.line_no, err.message), file=sys.stderr)
        print("Assembly failed with %d error(s); no output written."
              % len(errors), file=sys.stderr)
        return 1

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(binary) + ("\n" if binary else ""))
    except OSError as exc:
        print("Error: cannot write '%s': %s" % (out_path, exc), file=sys.stderr)
        return 1

    print("Assembled %d instructions -> %s" % (len(binary), out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
