import argparse
import json

from ralpdfassistant.clients.embeddings import get_embedder
from ralpdfassistant.core import ask
from ralpdfassistant.database import SessionLocal

TOP = (1, 3, 6)


def first_rank(hits, pages):
    return next((i + 1 for i, h in enumerate(hits) if h.page in pages), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc-id", type=int, required=True)
    ap.add_argument("--questions", default="eval/questions.json")
    args = ap.parse_args()

    data = json.load(open(args.questions, encoding="utf-8"))
    embedder = get_embedder()
    ranks = {False: [], True: []}

    with SessionLocal() as session:
        for item in data["good"]:
            for hybrid in (False, True):
                hits = ask.retrieve(session, embedder, item["q"], [args.doc_id], limit=30, hybrid=hybrid)
                ranks[hybrid].append(first_rank(hits, item["pages"]))

    print(f"{'вопрос':<70} вектор  гибрид")
    for item, v, h in zip(data["good"], ranks[False], ranks[True], strict=True):
        print(f"{item['q'][:68]:<70} {str(v):>6}  {str(h):>6}")

    n = len(data["good"])
    for name, key in (("вектор", False), ("гибрид", True)):
        r = ranks[key]
        row = ", ".join(f"топ-{k}: {sum(1 for x in r if x and x <= k)}" for k in TOP)
        mrr = sum(1 / x for x in r if x) / n
        print(f"{name}: {row} из {n}, MRR {mrr:.3f}")


if __name__ == "__main__":
    main()
