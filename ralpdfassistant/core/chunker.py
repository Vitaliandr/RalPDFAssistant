import re


def split_text(text: str, size: int = 800, overlap: int = 150) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []

    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n\n", text) if p.strip()]

    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for part in parts:
        #длиннее чанка, режем грубо
        while len(part) > size:
            if cur:
                chunks.append(" ".join(cur))
                cur, cur_len = [], 0
            chunks.append(part[:size])
            part = part[size - overlap :]

        if cur_len + len(part) > size and cur:
            chunks.append(" ".join(cur))
            tail: list[str] = []
            tail_len = 0
            for s in reversed(cur):
                if tail_len + len(s) + 1 > overlap:
                    break
                tail.insert(0, s)
                tail_len += len(s) + 1
            if tail_len + len(part) > size:
                tail, tail_len = [], 0
            cur, cur_len = tail, tail_len

        cur.append(part)
        cur_len += len(part) + 1

    if cur:
        chunks.append(" ".join(cur))
    return chunks
