"""Speech disfluency and filler word removal pipeline."""

import re
from typing import Set

# Common Whisper tokenizer IDs for filler words in large-v3-turbo / base / small
FILLER_TOKEN_IDS = {
    449,    # 'um'
    1105,   # ' um'
    3232,   # 'uh'
    2232,   # ' uh'
    40879,  # 'umm'
    29256,  # ' uhh'
    260,    # 'er'
    1189,   # ' er'
    545,    # 'ah'
    3716,   # ' ah'
}

# Standalone hesitation sounds (pure vocal pauses)
HESITATION_REGEX = re.compile(
    r'\b(?i:um+|uh+|umm+|uhh+|er|ah+|erm+|hmm?)\b',
    flags=re.IGNORECASE,
)


def clean_transcript(
    text: str,
    strip_fillers: bool = True,
    clean_conversational: bool = False,
) -> str:
    """Strip hesitation sounds, stutters, and clean up punctuation/capitalization.

    NOTE: Conversational phrases like 'you know', 'like', 'etc' are NEVER stripped.
    """
    if not text:
        return ""

    cleaned = text

    if strip_fillers:
        # Remove standalone hesitation sounds: um, uh, er, ah, hmm
        cleaned = re.sub(r'[,;\s]*' + HESITATION_REGEX.pattern + r'[,;\s]*', ' ', cleaned)

        # Fix repeated stuttered words (e.g. 'I, I think', 'the the script')
        cleaned = re.sub(r'\b([A-Za-z]+)\s+\1\b', r'\1', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b([A-Za-z]+)\s*,\s*\1\b', r'\1', cleaned, flags=re.IGNORECASE)

    # Clean up spacing before punctuation
    cleaned = re.sub(r'\s+([,.\?!;:])', r'\1', cleaned)

    # Clean up duplicate/consecutive commas or semicolons
    cleaned = re.sub(r'([,;])\s*([,;])+', r'\1', cleaned)

    # Remove leading punctuation (e.g. if leading 'Um, ' was stripped leaving ', hello')
    cleaned = re.sub(r'^\s*[,;\.\?!]+\s*', '', cleaned)

    # Normalize whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Ensure first character is properly capitalized if it was lowercased by leading filler strip
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]

    return cleaned
