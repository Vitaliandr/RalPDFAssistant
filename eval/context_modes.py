import argparse
import json
import time

from eval.answers import check_answers
from eval.search_modes import first_rank
from ralpdfassistant.clients.embeddings import get_embedder
from ralpdfassistant.core import ask, ingest
from ralpdfassistant.database import SessionLocal
from ralpdfassistant.repositories import documents as documents_repo
from ralpdfassistant.settings import settings
from ralpdfassistant.tables import Document

MODES = ("off", "title", "head")
#названия как у нормальных файлов
TITLES = {"report": "Отчётность Сегежа Групп за 6 месяцев 2026", "tariffs": "Тарифы расчётной карты ТПС 1.8"}


def retrieval_stats(session, embedder, questions, doc_id, hybrid):
    ranks = []
    for item in questions:
        hits = ask.retrieve(session, embedder, item["q"], [doc_id], limit=30, hybrid=hybrid)
        ranks.append(first_rank(hits, item["pages"]))
    top = [sum(1 for r in ranks if r and r <= k) for k in (1, 3, 6)]
    mrr = sum(1 / r for r in ranks if r) / len(ranks)
    return top, mrr


def run_mode(mode, args, embedder, questions, answers):
    settings.chunk_context = mode
    ids = {}
    with SessionLocal() as session:
        try:
            for key, path in (("report", args.report), ("tariffs", args.tariffs)):
                doc = Document(title=TITLES[key], path=path)
                documents_repo.add(session, doc)
                session.commit()
                ids[key] = doc.id
                ingest.process(session, embedder, doc.id)
            session.expire_all()
            chunks = {k: documents_repo.get(session, i).chunks_count for k, i in ids.items()}

            vec = retrieval_stats(session, embedder, questions, ids["report"], hybrid=False)
            hyb = retrieval_stats(session, embedder, questions, ids["report"], hybrid=True)
            print(f"[{mode}] поиск по отчётности посчитан, перехожу к ответам по тарифам", flush=True)
            passed = check_answers(session, embedder, answers, list(ids.values()), args.model, args.pause, quiet=True)
            return {"mode": mode, "chunks": chunks, "vector": vec, "hybrid": hyb, "answers": passed}
        finally:
            session.rollback()
            for doc_id in ids.values():
                doc = documents_repo.get(session, doc_id)
                if doc is not None:
                    documents_repo.delete(session, doc)
            session.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True, help="pdf отчётности (вопросы eval/questions.json)")
    ap.add_argument("--tariffs", required=True, help="pdf тарифов (вопросы eval/answers_tariffs.json)")
    ap.add_argument("--model", default="groq", help="ollama или groq (для groq нужна переменная GROQ_API_KEY)")
    ap.add_argument("--pause", type=float, default=12)
    ap.add_argument("--modes", nargs="+", default=list(MODES))
    args = ap.parse_args()

    questions = json.load(open("eval/questions.json", encoding="utf-8"))["good"]
    answers = json.load(open("eval/answers_tariffs.json", encoding="utf-8"))
    embedder = get_embedder()

    results = []
    for mode in args.modes:
        t0 = time.time()
        results.append(run_mode(mode, args, embedder, questions, answers))
        print(f"[{mode}] готово за {time.time() - t0:.0f} с", flush=True)

    n, m = len(questions), len(answers)
    print()
    print("режим | чанков | вектор: топ1/3/6, MRR | гибрид: топ1/3/6, MRR | ответов по тарифам")
    for r in results:
        v, vm = r["vector"]
        h, hm = r["hybrid"]
        print(
            f"{r['mode']:<5} | {r['chunks']['report']:>3}+{r['chunks']['tariffs']} | "
            f"{v[0]}/{v[1]}/{v[2]} из {n}, {vm:.3f} | {h[0]}/{h[1]}/{h[2]} из {n}, {hm:.3f} | {r['answers']} из {m}"
        )


if __name__ == "__main__":
    main()
