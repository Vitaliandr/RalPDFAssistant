import pytest

from app.config import Settings


def make(**kw):
    # _env_file=None чтоб не подхватить настоящий .env
    return Settings(_env_file=None, **kw)


def test_ollama_defaults():
    s = make(llm_provider="ollama")
    assert "11434" in s.llm_base_url
    assert s.llm_model


def test_groq_needs_key():
    with pytest.raises(ValueError):
        make(llm_provider="groq", llm_api_key="")


def test_groq_with_key():
    s = make(llm_provider="groq", llm_api_key="k")
    assert "groq.com" in s.llm_base_url


def test_model_override():
    s = make(llm_provider="gemini", llm_api_key="k", llm_model="gemini-2.5-flash")
    assert s.llm_model == "gemini-2.5-flash"


def test_unknown_provider():
    with pytest.raises(ValueError):
        make(llm_provider="abc")


def test_custom_needs_url_and_model():
    with pytest.raises(ValueError):
        make(llm_provider="custom")
