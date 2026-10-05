import argparse
import json
import re
import time

from ralpdfassistant.clients.embeddings import get_embedder
from ralpdfassistant.clients.llm import ask_llm
from ralpdfassistant.core import ask
from ralpdfassistant.database import SessionLocal
from ralpdfassistant.errors import LlmUnavailable


def norm(text):
    #без пробелов и неразрывных пробелов, "50 000" и "50000" считаем одним и тем же
    return re.sub(r"\s+", "", text.lower().replace(" ", " ").replace(" ", " "))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default="eval/answers_tariffs.json")
    ap.add_argument("--doc-id", type=int, action="append", help="по умолчанию ищем по всем документам")
    ap.add_argument("--pause", type=float, default=12, help="пауза между вопросами, чтобы не упереться в лимит")
    args = ap.parse_args()

    data = json.load(open(args.questions, encoding="utf-8"))
    embedder = get_embedder()
    passed = 0

    with SessionLocal() as session:
        for item in data:
            for _ in range(3):
                try:
                    text, hits = ask.answer(session, embedder, ask_llm, item["q"], args.doc_id)
                    break
                except LlmUnavailable as e:
                    #у облачных провайдеров бывают 503 и 429, ждём и пробуем ещё раз
                    print("   ", e.message, "- повтор через 25 с")
                    time.sleep(25)
            else:
                text = ""
            ok = all(norm(e) in norm(text) for e in item["expect"])
            passed += ok
            print(f"{'ок ' if ok else 'НЕТ'} {item['q'][:62]:<64} -> {text[:90]!r}")
            time.sleep(args.pause)

    print(f"верных ответов: {passed} из {len(data)}")


if __name__ == "__main__":
    main()
