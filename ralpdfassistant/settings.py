from dataclasses import dataclass
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# (размер, префикс вопроса, префикс куска)
#e5 без префиксов хуже
EMBED_MODELS = {
    "intfloat/multilingual-e5-large": (1024, "query: ", "passage: "),
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": (384, "", ""),
}

#по умолчанию локальная
DEFAULT_MODEL = "ollama"


@dataclass(frozen=True)
class LlmProfile:
    id: str
    label: str
    base_url: str
    model: str
    note: str
    #ключ приходит с вопросом
    cloud: bool = False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://rag:rag_pass@localhost:5432/rag"
    redis_url: str = "redis://localhost:6379/0"

    ollama_base_url: str = "http://host.docker.internal:11434/v1"
    ollama_model: str = "qwen2.5:7b"
    groq_model: str = "openai/gpt-oss-120b"

    embed_model: str = "intfloat/multilingual-e5-large"
    # считаются из embed_model
    embed_dim: int = 0
    query_prefix: str = ""
    passage_prefix: str = ""
    models_dir: str = "data/models"

    uploads_dir: str = "data/uploads"
    max_upload_mb: int = 20

    chunk_size: int = 800
    chunk_overlap: int = 150
    top_k: int = 6
    # off / title / head, по замеру лучше off
    chunk_context: Literal["off", "title", "head"] = "off"
    #гибрид, кандидатов с запасом
    hybrid: bool = True
    candidates: int = 30

    docs: bool = True
    log_json: bool = False

    def llm_profiles(self) -> dict[str, LlmProfile]:
        return {
            "ollama": LlmProfile(
                "ollama",
                "Локально (Ollama)",
                self.ollama_base_url,
                self.ollama_model,
                "Всё считается на этом компьютере, ничего не уходит в интернет",
            ),
            "groq": LlmProfile(
                "groq",
                "Облако (Groq)",
                "https://api.groq.com/openai/v1",
                self.groq_model,
                "В облако уходят вопрос и найденные фрагменты, файлы целиком не уходят",
                cloud=True,
            ),
        }

    @model_validator(mode="after")
    def fill_embed(self) -> "Settings":
        if self.embed_model not in EMBED_MODELS:
            raise ValueError("неизвестная EMBED_MODEL, доступны: " + ", ".join(EMBED_MODELS))
        self.embed_dim, self.query_prefix, self.passage_prefix = EMBED_MODELS[self.embed_model]
        return self


settings = Settings()
