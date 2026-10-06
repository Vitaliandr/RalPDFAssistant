from collections.abc import Callable

import httpx

from ralpdfassistant.errors import AppError, LlmUnavailable
from ralpdfassistant.settings import DEFAULT_MODEL, LlmProfile, settings

#в тестах подменяем
Llm = Callable[[str, str, str | None, str | None], str]

SYSTEM_PROMPT = (
    "Ты помощник, который отвечает на вопросы по документам. "
    "Отвечай только на основе приведённых фрагментов, ничего не выдумывай. "
    "Если ответа во фрагментах нет, так и скажи: в документах этого не нашлось. "
    "Отвечай по-русски, коротко и по делу. Цифры, суммы и сроки бери точно как в тексте. "
    "Единицы измерения (рубли, тысячи, миллионы) называй только если они прямо написаны во фрагментах, "
    "иначе назови одно число. Ссылки на источники в ответ не вставляй, они показываются отдельно."
)


def _status_text(code: int, profile: LlmProfile) -> str:
    if code in (401, 403):
        return "Провайдер не принял ключ, проверь его"
    if code == 429:
        return "Упёрлись в лимит бесплатного тарифа, подожди минуту"
    if code == 404 and not profile.cloud:
        # 404 у ollama = модель не скачана
        return f"Модель не скачана в Ollama: выполни в терминале ollama pull {profile.model}"
    if code == 404:
        return "Провайдер не знает такую модель, проверь название в настройках GROQ_MODEL"
    return f"Модель вернула ошибку {code}"


def _unreachable_text(profile: LlmProfile) -> str:
    if profile.cloud:
        return f"Не достучались до модели ({profile.label}), проверь интернет"
    return (
        "Не достучались до локальной модели. Запусти Ollama (ollama.com) и скачай модель командой "
        f"ollama pull {profile.model}, либо выбери Groq и вставь свой ключ"
    )


def clean_key(key: str) -> str:
    key = key.strip()
    #в заголовок, пробелы нельзя
    if not key or len(key) > 200 or any(c.isspace() or not c.isprintable() for c in key):
        raise AppError("Ключ выглядит неправильно, вставь его целиком без пробелов")
    return key


def ask_llm(
    question: str,
    context: str,
    model: str | None = None,
    api_key: str | None = None,
    client: httpx.Client | None = None,
) -> str:
    profile = settings.llm_profiles().get(model or DEFAULT_MODEL)
    if profile is None:
        raise AppError("Эта модель недоступна: неизвестное имя")

    headers = {}
    if profile.cloud:
        if not api_key:
            raise AppError("Для облачной модели нужен ключ: вставь свой в панели «Ключ» вверху страницы")
        headers["Authorization"] = f"Bearer {clean_key(api_key)}"

    body = {
        "model": profile.model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Фрагменты документов:\n\n{context}\n\nВопрос: {question}"},
        ],
    }
    # на cpu долго, таймаут большой
    http = client or httpx.Client(timeout=600)
    try:
        resp = http.post(f"{profile.base_url}/chat/completions", json=body, headers=headers)
        resp.raise_for_status()
        return str(resp.json()["choices"][0]["message"]["content"]).strip()
    except httpx.HTTPStatusError as e:
        raise LlmUnavailable(_status_text(e.response.status_code, profile)) from None
    except httpx.HTTPError:
        raise LlmUnavailable(_unreachable_text(profile)) from None
    except (KeyError, IndexError, ValueError):
        raise LlmUnavailable("Модель вернула ответ в непонятном виде") from None
    finally:
        if client is None:
            http.close()
