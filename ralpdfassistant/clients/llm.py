from collections.abc import Callable

import httpx

from ralpdfassistant.errors import AppError, LlmUnavailable
from ralpdfassistant.settings import LlmProfile, settings

#вопрос, контекст, id модели (None значит по умолчанию), свой ключ пользователя (None значит из .env).
# отдаёт текст ответа, в тестах подменяется
Llm = Callable[[str, str, str | None, str | None], str]

SYSTEM_PROMPT = (
    "Ты помощник, который отвечает на вопросы по документам. "
    "Отвечай только на основе приведённых фрагментов, ничего не выдумывай. "
    "Если ответа во фрагментах нет, так и скажи: в документах этого не нашлось. "
    "Отвечай по-русски, коротко и по делу. Цифры, суммы и сроки бери точно как в тексте. "
    "Единицы измерения (рубли, тысячи, миллионы) называй только если они прямо написаны во фрагментах, "
    "иначе назови одно число. Ссылки на источники в ответ не вставляй, они показываются отдельно."
)


def _status_text(code: int, own_key: bool, profile: LlmProfile) -> str:
    if code in (401, 403):
        return "Провайдер не принял ключ, проверь его" if own_key else "Провайдер не принял ключ, проверь ключ в .env"
    if code == 429:
        return "Упёрлись в лимит бесплатного тарифа, подожди минуту"
    if code == 404 and not profile.cloud:
        #ollama отвечает 404 когда модель не скачана, это самое частое у нового человека
        return f"Модель не скачана в Ollama: выполни в терминале ollama pull {profile.model}"
    if code == 404:
        return "Провайдер не знает такую модель, проверь название модели в .env"
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
    #в заголовок уходит как есть, поэтому пробелы и переводы строк внутри ключа сразу отсекаем
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
    profile = settings.llm_profiles().get(model or settings.default_llm)
    if profile is None:
        raise AppError("Эта модель недоступна: неизвестное имя")

    #свой ключ пользователя важнее чем из .env, но только для облачных моделей
    own_key = bool(api_key) and profile.cloud
    key = clean_key(api_key) if own_key and api_key else profile.api_key
    if profile.cloud and not key:
        raise AppError("Для облачной модели нужен ключ: вставь свой в панели «Ключ» вверху страницы")

    headers = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    body = {
        "model": profile.model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Фрагменты документов:\n\n{context}\n\nВопрос: {question}"},
        ],
    }
    #на cpu 7b думает долго, таймаут большой
    http = client or httpx.Client(timeout=600)
    try:
        resp = http.post(f"{profile.base_url}/chat/completions", json=body, headers=headers)
        resp.raise_for_status()
        return str(resp.json()["choices"][0]["message"]["content"]).strip()
    except httpx.HTTPStatusError as e:
        raise LlmUnavailable(_status_text(e.response.status_code, own_key, profile)) from None
    except httpx.HTTPError:
        raise LlmUnavailable(_unreachable_text(profile)) from None
    except (KeyError, IndexError, ValueError):
        raise LlmUnavailable("Модель вернула ответ в непонятном виде") from None
    finally:
        if client is None:
            http.close()
