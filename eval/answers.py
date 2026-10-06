import argparse
import json
import os
import re
import time

from ralpdfassistant.clients.embeddings import get_embedder
from ralpdfassistant.clients.llm import ask_llm
from ralpdfassistant.core import ask
from ralpdfassistant.database import SessionLocal
from ralpdfassistant.errors import LlmUnavailable


def norm(text):
    # 50 000 и 50000 одно и то же
    return re.sub(r"\s+", "", text.lower())


def env_key():
    #ключ только для замеров
    return os.environ.get("GROQ_API_KEY") or None


def check_answers(session, embedder, data, doc_ids, model, pause, quiet=False):
    passed = 0
    for item in data:
        for _ in range(3):
            try:
                text, _hits = ask.answer(session, embedder, ask_llm, item["q"], doc_ids, model, env_key())
                break
            except LlmUnavailable as e:
                # groq иногда отдаёт 503, ждём
                print("   ", e.message, "- повтор через 25 с", flush=True)
                time.sleep(25)
        else:
            text = ""
        ok = all(norm(e) in norm(text) for e in item["expect"])
        passed += ok
        if not quiet:
            print(f"{'ок ' if ok else 'НЕТ'} {item['q'][:62]:<64} -> {text[:90]!r}", flush=True)
        time.sleep(pause)
    return passed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default="eval/answers_tariffs.json")
    ap.add_argument("--doc-id", type=int, action="append", help="по умолчанию ищем по всем документам")
    ap.add_argument("--pause", type=float, default=12, help="пауза между вопросами, чтобы не упереться в лимит")
    ap.add_argument("--model", default="groq", help="ollama или groq (для groq нужна переменная GROQ_API_KEY)")
    args = ap.parse_args()

    data = json.load(open(args.questions, encoding="utf-8"))
    with SessionLocal() as session:
        passed = check_answers(session, get_embedder(), data, args.doc_id, args.model, args.pause)
    print(f"верных ответов: {passed} из {len(data)}")


if __name__ == "__main__":
    main()
