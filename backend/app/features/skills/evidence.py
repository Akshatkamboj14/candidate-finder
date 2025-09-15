# backend/app/utils/evidence.py
"""
Centralized evidence extractor for tech patterns (e.g. PyTorch / CNN).
Both github connectors should import and use extract_evidence_from_text()
to avoid duplicate code and inconsistent behavior.
"""

import re
from typing import List

_PYTORCH_PATTERNS = [
    r"\bimport\s+torch\b",
    r"\bfrom\s+torch\b",
    r"\btorch\.",
    r"\bPyTorch\b",
    r"\bConv2d\b",
    r"\bConv3d\b",
    r"\bconvolutional\b",
    r"\bcnn\b",
    r"\bnn\.Module\b",
    r"\btorchvision\b",
    r"\bkeras\b",
    r"\btensorflow\b",
]


def extract_evidence_from_text(text: str) -> List[str]:
    """
    Returns a list of short snippets (deduped, order-preserving) that match
    any of the _PYTORCH_PATTERNS in the given text.
    """
    if not text:
        return []

    evidence = []
    for pattern in _PYTORCH_PATTERNS:
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            # capture some context around the match, but keep snippets reasonably short
            start = max(0, m.start() - 80)
            end = min(len(text), m.end() + 80)
            snippet = text[start:end].replace("\n", " ")
            evidence.append(snippet.strip())

    # dedupe while preserving order
    seen = set()
    out = []
    for e in evidence:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out
