"""Recursive character chunking with overlap.

Strategy: split on the strongest separator
available (paragraph → line → sentence → word) so chunks follow the document's
natural structure, then merge pieces up to `chunk_size` characters with
`chunk_overlap` characters of context carried between neighbours. Sizes are in
characters, not tokens — deterministic, tokenizer-independent, and good enough
to tune empirically against the eval harness.
"""

from __future__ import annotations

from dataclasses import dataclass

_SEPARATORS = ["\n\n", "\n", ". ", " "]


@dataclass(frozen=True, slots=True)
class Chunk:
    text: str
    index: int


def _split(text: str, separators: list[str], chunk_size: int) -> list[str]:
    """Recursively split `text` into pieces no longer than `chunk_size`."""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    if not separators:
        # No separator left — hard cut.
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    sep, rest = separators[0], separators[1:]
    parts = [p for p in text.split(sep) if p.strip()]
    if len(parts) <= 1:
        return _split(text, rest, chunk_size)

    pieces: list[str] = []
    for part in parts:
        candidate = part if sep in (" ",) else part + sep.rstrip("\n")
        if len(candidate) > chunk_size:
            pieces.extend(_split(part, rest, chunk_size))
        else:
            pieces.append(part)
    return pieces


def chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 120) -> list[Chunk]:
    """Split `text` into overlapping chunks of at most `chunk_size` characters."""
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    pieces = _split(text.strip(), _SEPARATORS, chunk_size)

    # Merge small pieces into chunks, carrying overlap from the previous chunk.
    chunks: list[Chunk] = []
    current = ""
    for piece in pieces:
        candidate = f"{current} {piece}".strip() if current else piece.strip()
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            chunks.append(Chunk(text=current, index=len(chunks)))
            tail = current[-chunk_overlap:] if chunk_overlap else ""
            current = f"{tail} {piece}".strip()
            # If even the overlap+piece exceeds the budget, flush the piece alone.
            if len(current) > chunk_size:
                current = piece.strip()[:chunk_size]
        else:
            current = piece.strip()[:chunk_size]
    if current:
        chunks.append(Chunk(text=current, index=len(chunks)))
    return chunks
