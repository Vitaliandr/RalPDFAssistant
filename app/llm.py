import httpx

from app.config import settings

SYSTEM_PROMPT = (
    "Ты помощник, который отвечает на вопросы по документам. "
    "Отвечай только на основе приведённых фрагментов, ничего не выдумывай. "
    "Если ответа во фрагментах нет, так и скажи: в документах этого не нашлось. "
    "Отвечай по-русски, коротко и по делу. Цифры, суммы и сроки бери точно как в тексте."
)


def build_context(found) -> str:
    lines = []
    for n, (chunk, title, _) in enumerate(found, start=1):
        where = f"{title}, стр. {chunk.page}" if chunk.page else title
        lines.append(f"[{n}] ({where})\n{chunk.text}")
    return "\n\n".join(lines)


def ask_llm(question: str, context: str) -> str:
    headers = {}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    body = {
        "model": settings.llm_model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Фрагменты документов:\n\n{context}\n\nВопрос: {question}"},
        ],
    }
    #на cpu 7b думает долго, таймаут большой
    resp = httpx.post(
        f"{settings.llm_base_url}/chat/completions", json=body, headers=headers, timeout=600
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()
