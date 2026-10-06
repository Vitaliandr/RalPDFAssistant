import pytest

from ralpdfassistant.settings import DEFAULT_MODEL, Settings


def make(**kw: object) -> Settings:
    # без настоящего .env
    return Settings(_env_file=None, **kw)  # type: ignore[arg-type]


def test_e5_dim_and_prefixes():
    s = make()
    assert s.embed_dim == 1024
    assert s.query_prefix == "query: "
    assert s.passage_prefix == "passage: "


def test_minilm_has_no_prefixes():
    s = make(embed_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    assert s.embed_dim == 384
    assert s.query_prefix == ""


def test_unknown_embed_model():
    with pytest.raises(ValueError):
        make(embed_model="что-то/левое")


def test_two_models_local_and_groq():
    profiles = make().llm_profiles()
    assert list(profiles) == ["ollama", "groq"]
    assert DEFAULT_MODEL == "ollama"
    assert "11434" in profiles["ollama"].base_url
    assert "groq.com" in profiles["groq"].base_url


def test_only_groq_is_cloud():
    profiles = make().llm_profiles()
    assert profiles["groq"].cloud is True
    assert profiles["ollama"].cloud is False


def test_models_can_be_changed():
    s = make(ollama_model="llama3.1:8b", groq_model="llama-3.3-70b-versatile", ollama_base_url="http://pc:11434/v1")
    profiles = s.llm_profiles()
    assert profiles["ollama"].model == "llama3.1:8b"
    assert profiles["ollama"].base_url == "http://pc:11434/v1"
    assert profiles["groq"].model == "llama-3.3-70b-versatile"


def test_no_api_keys_in_settings():
    #ключей в настройках быть не должно
    fields = Settings.model_fields
    assert not [name for name in fields if "api_key" in name or name.endswith("_key")]


def test_notes_say_what_leaves_the_machine():
    profiles = make().llm_profiles()
    assert "не уходит" in profiles["ollama"].note
    assert "уходят вопрос" in profiles["groq"].note
