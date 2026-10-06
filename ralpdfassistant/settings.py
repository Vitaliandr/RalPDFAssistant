from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#готовые адреса и модели, чтобы в .env хватало одной строки
PROVIDERS = {
    "ollama": ("http://host.docker.internal:11434/v1", "qwen2.5:7b"),
    "groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-120b"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.0-flash"),
}

# модель: (размер вектора, префикс вопроса, префикс куска текста)
# e5 учили с префиксами, без них она заметно хуже
EMBED_MODELS = {
    "intfloat/multilingual-e5-large": (1024, "query: ", "passage: "),
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": (384, "", ""),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://rag:rag_pass@localhost:5432/rag"
    redis_url: str = "redis://localhost:6379/0"

    llm_provider: str = "ollama"
    # если заданы руками то перебивают значения из PROVIDERS
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: str = ""

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

    @model_validator(mode="after")
    def fill_embed(self) -> "Settings":
        if self.embed_model not in EMBED_MODELS:
            raise ValueError("неизвестная EMBED_MODEL, доступны: " + ", ".join(EMBED_MODELS))
        self.embed_dim, self.query_prefix, self.passage_prefix = EMBED_MODELS[self.embed_model]
        return self

    @model_validator(mode="after")
    def fill_llm(self) -> "Settings":
        name = self.llm_provider.lower()
        if name == "custom":
            if not (self.llm_base_url and self.llm_model):
                raise ValueError("для custom нужны LLM_BASE_URL и LLM_MODEL")
            return self
        if name not in PROVIDERS:
            raise ValueError(f"неизвестный LLM_PROVIDER: {self.llm_provider}")

        url, model = PROVIDERS[name]
        self.llm_base_url = self.llm_base_url or url
        self.llm_model = self.llm_model or model
        # без ключа облачный провайдер всё равно ответит 401, лучше упасть на старте
        if name != "ollama" and not self.llm_api_key:
            raise ValueError(f"для {name} нужен LLM_API_KEY")
        return self


settings = Settings()
