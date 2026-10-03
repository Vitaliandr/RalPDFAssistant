from pydantic import model_validator
from pydantic_settings import BaseSettings

# готовые адреса и модели, чтоб в .env хватало одной строки
PROVIDERS = {
    "ollama": ("http://host.docker.internal:11434/v1", "qwen2.5:7b"),
    "groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-120b"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.0-flash"),
}


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://rag:rag_pass@localhost:5432/rag"
    redis_url: str = "redis://localhost:6379/0"

    llm_provider: str = "ollama"
    # если заданы руками, перебивают то что в PROVIDERS
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: str = ""

    embed_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embed_dim: int = 384
    models_dir: str = "data/models"

    uploads_dir: str = "data/uploads"
    max_upload_mb: int = 20

    chunk_size: int = 800
    chunk_overlap: int = 150
    top_k: int = 5

    @model_validator(mode="after")
    def fill_llm(self):
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
        if name != "ollama" and not self.llm_api_key:
            raise ValueError(f"для {name} нужен LLM_API_KEY")
        return self


settings = Settings()
