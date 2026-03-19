"""
Text cleaning utilities applied after document parsing.
Removes boilerplate, excessive whitespace, and non-informative lines.
"""

import re

# Common corporate document boilerplate patterns
_BOILERPLATE_PATTERNS = [
    re.compile(r"©\s*\S+.*?(All\s+rights?\s+reserved\.?)?", re.IGNORECASE),
    re.compile(r"confidential\s*(–|—|-|:).*", re.IGNORECASE),
    re.compile(r"page\s+\d+\s*(of\s+\d+)?", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*$"),  # lone page numbers
]

_WHITESPACE_RE = re.compile(r"\n{3,}")


def clean(text: str) -> str:
    """Normalise and clean extracted document text."""
    if not text:
        return ""

    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue
        skip = any(p.search(stripped) for p in _BOILERPLATE_PATTERNS)
        if not skip:
            cleaned.append(stripped)

    result = "\n".join(cleaned)
    result = _WHITESPACE_RE.sub("\n\n", result)
    return result.strip()
