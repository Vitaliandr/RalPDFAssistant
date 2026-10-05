import pytest

from ralpdfassistant.settings import Settings


def make(**kw: object) -> Settings:
    # _env_file=None чтобы не подхватить настоящий .env
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


def test_custom_ok():
    s = make(llm_provider="custom", llm_base_url="http://x/v1", llm_model="m")
    assert s.llm_model == "m"
