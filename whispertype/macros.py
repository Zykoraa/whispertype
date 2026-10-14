"""Spoken syntax macros and verbal formatting commands."""

import re
from typing import Tuple


SCRATCH_THAT_MARKER = "__ACTION_SCRATCH_THAT__"


def _to_snake_case(phrase: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", phrase)
    return "_".join(w.lower() for w in words)


def _to_camel_case(phrase: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", phrase)
    if not words:
        return ""
    return words[0].lower() + "".join(w.capitalize() for w in words[1:])


def _to_pascal_case(phrase: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", phrase)
    return "".join(w.capitalize() for w in words)


def _to_kebab_case(phrase: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", phrase)
    return "-".join(w.lower() for w in words)


def _to_screaming_snake(phrase: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", phrase)
    return "_".join(w.upper() for w in words)


CASING_PATTERNS = [
    (re.compile(r'\b(?i:screaming snake case|constant case)\s+([a-zA-Z0-9\s]+?)(?=[,.\?!;:]|$)', re.IGNORECASE), _to_screaming_snake),
    (re.compile(r'\b(?i:snake case)\s+([a-zA-Z0-9\s]+?)(?=[,.\?!;:]|$)', re.IGNORECASE), _to_snake_case),
    (re.compile(r'\b(?i:camel case)\s+([a-zA-Z0-9\s]+?)(?=[,.\?!;:]|$)', re.IGNORECASE), _to_camel_case),
    (re.compile(r'\b(?i:pascal case)\s+([a-zA-Z0-9\s]+?)(?=[,.\?!;:]|$)', re.IGNORECASE), _to_pascal_case),
    (re.compile(r'\b(?i:kebab case)\s+([a-zA-Z0-9\s]+?)(?=[,.\?!;:]|$)', re.IGNORECASE), _to_kebab_case),
]

SYMBOL_REPLACEMENTS = [
    (re.compile(r'\b(?i:greater than or equal to)\b'), ">="),
    (re.compile(r'\b(?i:less than or equal to)\b'), "<="),
    (re.compile(r'\b(?i:not equals|not equal to)\b'), "!="),
    (re.compile(r'\b(?i:equals equals|is equal to)\b'), "=="),
    (re.compile(r'\b(?i:fat arrow)\b'), "=>"),
    (re.compile(r'\b(?i:skinny arrow|thin arrow|arrow)\b'), "->"),
    (re.compile(r'\b(?i:new paragraph)\b'), "\n\n"),
    (re.compile(r'\b(?i:new line|newline)\b'), "\n"),
    (re.compile(r'\b(?i:tab|indent)\b'), "\t"),
]


def process_macros(text: str, enabled: bool = True) -> Tuple[str, bool]:
    """Parse verbal formatting commands and check for deletion actions.

    Returns:
        (transformed_text, is_scratch_that)
    """
    if not text or not enabled:
        return text, False

    clean_check = text.lower().strip(".!?, ")
    if clean_check in ("scratch that", "delete that", "undo that", "cancel that"):
        return SCRATCH_THAT_MARKER, True

    res = text

    # Apply casings: snake case, camel case, etc.
    for pattern, func in CASING_PATTERNS:
        res = pattern.sub(lambda m: func(m.group(1)), res)

    # Apply symbol macros: new line, arrows, operators
    for pattern, repl in SYMBOL_REPLACEMENTS:
        res = pattern.sub(repl, res)

    # Clean up spaces around newlines
    res = re.sub(r'[ \t]*\n[ \t]*', '\n', res)

    return res, False
