from dataclasses import dataclass
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# модель: (размер вектора, префикс вопроса, префикс куска текста)
# e5 учили с префиксами, без них она заметно хуже
EMBED_MODELS = {
    "intfloat/multilingual-e5-large": (1024, "query: ", "passage: "),
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": (384, "", ""),
}


@dataclass(frozen=True)
class LlmProfile:
    id: str
    label: str
    base_url: str
    model: str
    api_key: str
    #что видит пользователь в интерфейсе: куда уходят данные
    note: str
    cloud: bool = False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://rag:rag_pass@localhost:5432/rag"
    redis_url: str = "redis://localhost:6379/0"

    # локальная модель есть всегда, облачные появляются в интерфейсе только если задан ключ
    ollama_base_url: str = "http://host.docker.internal:11434/v1"
    ollama_model: str = "qwen2.5:7b"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    #какая модель выбрана в интерфейсе по умолчанию. пусто значит groq если есть ключ, иначе локальная
    default_llm: str = ""

    embed_model: str = "intfloat/multilingual-e5-large"
    #эти три считаются из embed_model в валидаторе ниже
    embed_dim: int = 0
    query_prefix: str = ""
    passage_prefix: str = ""
    models_dir: str = "data/models"

    uploads_dir: str = "data/uploads"
    max_upload_mb: int = 20

    chunk_size: int = 800
    chunk_overlap: int = 150
    top_k: int = 6
    # что дописывать перед куском при подсчёте эмбеддинга: off ничего, title название и страницу,
    #head ещё и первые слова страницы (там обычно заголовок таблицы и единицы измерения)
    chunk_context: Literal["off", "title", "head"] = "title"
    #гибридный поиск: векторы плюс слова. кандидатов берём с запасом, потом склеиваем и режем до top_k
    hybrid: bool = True
    candidates: int = 30

    # swagger в проде лучше выключать
    docs: bool = True
    log_json: bool = False

    def llm_profiles(self) -> dict[str, LlmProfile]:
        profiles = {
            "ollama": LlmProfile(
                "ollama",
                "Локально (Ollama)",
                self.ollama_base_url,
                self.ollama_model,
                "",
                "Всё считается на этом компьютере, ничего не уходит в интернет",
            )
        }
        cloud_note = "В облако уходят вопрос и найденные фрагменты, файлы целиком не уходят"
        #groq есть в списке всегда: если ключа в .env нет, человек вставит свой прямо в интерфейсе
        profiles["groq"] = LlmProfile(
            "groq",
            "Облако (Groq)",
            "https://api.groq.com/openai/v1",
            self.groq_model,
            self.groq_api_key,
            cloud_note,
            cloud=True,
        )
        if self.gemini_api_key:
            profiles["gemini"] = LlmProfile(
                "gemini",
                "Облако (Gemini)",
                "https://generativelanguage.googleapis.com/v1beta/openai",
                self.gemini_model,
                self.gemini_api_key,
                cloud_note,
                cloud=True,
            )
        return profiles

    @model_validator(mode="after")
    def fill_embed(self) -> "Settings":
        if self.embed_model not in EMBED_MODELS:
            raise ValueError("неизвестная EMBED_MODEL, доступны: " + ", ".join(EMBED_MODELS))
        self.embed_dim, self.query_prefix, self.passage_prefix = EMBED_MODELS[self.embed_model]
        return self

    @model_validator(mode="after")
    def fill_default_llm(self) -> "Settings":
        profiles = self.llm_profiles()
        if not self.default_llm:
            self.default_llm = "groq" if self.groq_api_key else "ollama"
        profile = profiles.get(self.default_llm)
        #облачная модель по умолчанию без ключа в .env сломала бы каждый вопрос, лучше упасть на старте
        if profile is None or (profile.cloud and not profile.api_key):
            raise ValueError(f"DEFAULT_LLM={self.default_llm} не подходит: неизвестное имя или не задан ключ")
        return self


settings = Settings()
