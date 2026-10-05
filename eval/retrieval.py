import argparse
import json
import time
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

from app.chunker import split_text
from app.config import EMBED_MODELS, settings
from app.tasks import read_pages

def load_chunks(pdf):
    chunks = []
    for page, text in read_pages(Path(pdf)):
        for c in split_text(text, settings.chunk_size, settings.chunk_overlap):
            chunks.append((page, c))
    return chunks


def embed(model, texts):
    return np.array([v for v in model.embed(texts)])


def run(name, chunks, data):
    _, qp, pp = EMBED_MODELS.get(name, (0, "", ""))
    model = TextEmbedding(model_name=name, cache_dir=settings.models_dir)

    t0 = time.time()
    mat = embed(model, [pp + t for _, t in chunks])
    index_sec = time.time() - t0
    mat = mat / np.linalg.norm(mat, axis=1, keepdims=True)

    ranks = []
    q_times = []
    for item in data["good"]:
        t0 = time.time()
        q = embed(model, [qp + item["q"]])[0]
        q_times.append(time.time() - t0)
        sims = mat @ (q / np.linalg.norm(q))
        order = np.argsort(-sims)
        rank = next((i + 1 for i, idx in enumerate(order) if chunks[idx][0] in item["pages"]), None)
        ranks.append(rank)

    bad_scores = []
    for q in data["bad"]:
        v = embed(model, [qp + q])[0]
        bad_scores.append(float((mat @ (v / np.linalg.norm(v))).max()))

    n = len(ranks)
    good_scores = []
    for item in data["good"]:
        v = embed(model, [qp + item["q"]])[0]
        good_scores.append(float((mat @ (v / np.linalg.norm(v))).max()))

    print(f"\n== {name}")
    print(f"чанков {len(chunks)}, индексация {index_sec:.1f} с, вопрос {np.mean(q_times) * 1000:.0f} мс")
    for k in (1, 5, 10):
        print(f"  в топ-{k}: {sum(1 for r in ranks if r and r <= k)} из {n}")
    print(f"  MRR {np.mean([1 / r if r else 0 for r in ranks]):.3f}")
    print(f"  ранги: {ranks}")
    print(f"  лучший score на вопросах с ответом: {min(good_scores):.2f}..{max(good_scores):.2f}")
    print(f"  лучший score на вопросах без ответа: {min(bad_scores):.2f}..{max(bad_scores):.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--questions", default="eval/questions.json")
    ap.add_argument("--models", nargs="+", default=[settings.embed_model])
    args = ap.parse_args()

    data = json.load(open(args.questions, encoding="utf-8"))
    chunks = load_chunks(args.pdf)
    for m in args.models:
        run(m, chunks, data)
