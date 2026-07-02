from api.config import settings


def chunk_text(text: str, *, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    """Split text into overlapping fixed-size chunks, breaking on whitespace where possible."""
    size = chunk_size or settings.chunk_size
    gap = overlap if overlap is not None else settings.chunk_overlap
    if gap >= size:
        raise ValueError("overlap must be smaller than chunk_size")

    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + size, length)
        if end < length:
            boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        # guarantee forward progress even if a boundary made this a short chunk
        start = max(end - gap, start + 1)
    return chunks
