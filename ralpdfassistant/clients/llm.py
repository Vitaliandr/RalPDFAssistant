from collections.abc import Callable

import httpx

from ralpdfassistant.errors import LlmUnavailable
from ralpdfassistant.settings import settings

# принимает вопрос и контекст, отдаёт текст ответа. в тестах подменяется
Llm = Callable[[str, str], str]

SYSTEM_PROMPT = (
    "Ты помощник, который отвечает на вопросы по документам. "
    "Отвечай только на основе приведённых фрагментов, ничего не выдумывай. "
    "Если ответа во фрагментах нет, так и скажи: в документах этого не нашлось. "
    "Отвечай по-русски, коротко и по делу. Цифры, суммы и сроки бери точно как в тексте. "
    "Единицы измерения (рубли, тысячи, миллионы) называй только если они прямо написаны во фрагментах, "
    "иначе назови одно число. Ссылки на источники в ответ не вставляй, они показываются отдельно."
)


def _status_text(code: int) -> str:
    if code in (401, 403):
        return "Провайдер не принял ключ, проверь LLM_API_KEY"
    if code == 429:
        return "Упёрлись в лимит бесплатного тарифа, подожди минуту"
    if code == 404:
        return "Провайдер не знает такую модель, проверь LLM_MODEL"
    return f"Модель вернула ошибку {code}"


def ask_llm(question: str, context: str, client: httpx.Client | None = None) -> str:
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
    http = client or httpx.Client(timeout=600)
    try:
        resp = http.post(f"{settings.llm_base_url}/chat/completions", json=body, headers=headers)
        resp.raise_for_status()
        return str(resp.json()["choices"][0]["message"]["content"]).strip()
    except httpx.HTTPStatusError as e:
        raise LlmUnavailable(_status_text(e.response.status_code)) from None
    except httpx.HTTPError:
        raise LlmUnavailable("Не достучались до модели, проверь адрес и что ollama запущена") from None
    except (KeyError, IndexError, ValueError):
        raise LlmUnavailable("Модель вернула ответ в непонятном виде") from None
    finally:
        if client is None:
            http.close()
