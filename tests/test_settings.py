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


def test_without_keys_local_is_default_and_groq_waits_for_user_key():
    s = make()
    profiles = s.llm_profiles()
    assert list(profiles) == ["ollama", "groq"]
    assert s.default_llm == "ollama"
    assert "11434" in profiles["ollama"].base_url
    #ключа в .env нет, но модель в списке есть: человек вставит свой в интерфейсе
    assert profiles["groq"].cloud and profiles["groq"].api_key == ""


def test_groq_key_in_env_makes_it_default():
    s = make(groq_api_key="k")
    assert s.default_llm == "groq"
    assert "groq.com" in s.llm_profiles()["groq"].base_url
    assert s.llm_profiles()["groq"].api_key == "k"


def test_default_can_be_local_even_with_key():
    s = make(groq_api_key="k", default_llm="ollama")
    assert s.default_llm == "ollama"


def test_cloud_default_needs_key_in_env():
    #иначе каждый вопрос сразу упирался бы в отказ
    with pytest.raises(ValueError):
        make(default_llm="groq")


def test_unknown_default():
    with pytest.raises(ValueError):
        make(default_llm="abc")


def test_model_override():
    s = make(gemini_api_key="k", gemini_model="gemini-2.5-flash")
    assert s.llm_profiles()["gemini"].model == "gemini-2.5-flash"


def test_gemini_hidden_without_key():
    assert "gemini" not in make().llm_profiles()


def test_cloud_notes_say_what_leaves_the_machine():
    s = make(groq_api_key="k")
    profiles = s.llm_profiles()
    assert "не уходит" in profiles["ollama"].note
    assert "уходят вопрос" in profiles["groq"].note
