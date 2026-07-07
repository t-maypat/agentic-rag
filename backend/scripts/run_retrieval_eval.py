"""Deterministic retrieval eval + CI gate (REVAMP_PLAN §8.2, §8.4).

Runs the full hybrid pipeline (LocalNumpyStore dense + real BM25 + fusion) over the
committed embedding fixtures — zero network, zero LLM calls — and reports
recall@5/@10, MRR@10, and nDCG@10 overall and per category across the 35 answerable
golden-retrieval items. Unanswerable items report top raw dense cosine only.

Gate: exits non-zero when recall@5 drops more than 0.02 below the committed
baseline. Regenerate the baseline deliberately with ``--update-baselines``.

    uv run python scripts/run_retrieval_eval.py
    uv run python scripts/run_retrieval_eval.py --update-baselines
"""

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.adapters.vectorstore import LocalNumpyStore  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.eval.datasets import load_golden_retrieval  # noqa: E402
from app.eval.fixtures import assert_fixtures_current, load_query_embeddings  # noqa: E402
from app.eval.harness import evaluate_retrieval  # noqa: E402
from app.retrieval.bm25 import Bm25Index  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CHUNKS_PATH = REPO_ROOT / settings.chunks_path
GOLDEN_RETRIEVAL = REPO_ROOT / "data/eval/golden_retrieval.jsonl"
FIXTURE_DIR = REPO_ROOT / "data/eval/fixtures"
CORPUS_NPZ = FIXTURE_DIR / "corpus_embeddings.npz"
QUERY_NPZ = FIXTURE_DIR / "query_embeddings.npz"
BASELINES_PATH = REPO_ROOT / "data/eval/baselines.json"

METRIC_NAMES = ["recall@5", "recall@10", "mrr@10", "ndcg@10"]
GATE_METRIC = "recall@5"
GATE_TOLERANCE = 0.02


def _fmt_row(label: str, scores: dict, n: object = "") -> str:
    cells = "  ".join(f"{scores[name]:.3f}" for name in METRIC_NAMES)
    return f"  {label:<26} {str(n):>3}   {cells}"


def _print_report(report: dict) -> None:
    header = "  ".join(name for name in METRIC_NAMES)
    print("\nRetrieval eval (answerable items only)")
    print(f"  {'category':<26} {'n':>3}   {header}")
    print(_fmt_row("OVERALL", report["overall"], report["n_answerable"]))
    for category, summary in report["by_category"].items():
        scores = {name: summary[name] for name in METRIC_NAMES}
        print(_fmt_row(category, scores, summary["n"]))

    print(f"\nUnanswerable items ({report['n_unanswerable']}) — top raw dense cosine (ungated):")
    for row in report["unanswerable"]:
        cosine = row["top_dense_cosine"]
        cosine_str = f"{cosine:.3f}" if cosine is not None else "n/a"
        print(f"  {row['qid']:<10} {cosine_str}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic retrieval eval + gate.")
    parser.add_argument(
        "--update-baselines",
        action="store_true",
        help="Overwrite data/eval/baselines.json with the current overall metrics.",
    )
    args = parser.parse_args()

    missing = [p for p in (CORPUS_NPZ, QUERY_NPZ) if not p.exists()]
    if missing:
        names = ", ".join(p.name for p in missing)
        print(
            f"Missing eval fixtures: {names}\n"
            "Build them once (needs a valid GEMINI_API_KEY):\n"
            "  uv run python scripts/build_eval_fixtures.py"
        )
        return 1

    items = load_golden_retrieval(GOLDEN_RETRIEVAL)
    questions = [item["question"] for item in items]
    assert_fixtures_current(
        corpus_npz=CORPUS_NPZ,
        query_npz=QUERY_NPZ,
        chunks_path=CHUNKS_PATH,
        retrieval_questions=questions,
    )

    store = LocalNumpyStore.from_files(CORPUS_NPZ, CHUNKS_PATH)
    bm25 = Bm25Index.from_path(CHUNKS_PATH)
    query_vectors = load_query_embeddings(QUERY_NPZ).by_qid()

    report = evaluate_retrieval(items, store, bm25, query_vectors, settings.hybrid_alpha)
    _print_report(report)

    overall = report["overall"]
    if args.update_baselines:
        payload = {name: round(overall[name], 4) for name in METRIC_NAMES}
        BASELINES_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"\nUpdated baselines -> {BASELINES_PATH}")
        return 0

    if not BASELINES_PATH.exists():
        print("\nNo baselines.json found. Create it with --update-baselines.")
        return 1

    baselines = json.loads(BASELINES_PATH.read_text(encoding="utf-8"))
    baseline = baselines[GATE_METRIC]
    current = overall[GATE_METRIC]
    floor = baseline - GATE_TOLERANCE
    print(
        f"\nGate: {GATE_METRIC} = {current:.3f} "
        f"(baseline {baseline:.3f}, floor {floor:.3f}, tolerance {GATE_TOLERANCE})"
    )
    if current < floor:
        print("FAIL: retrieval regressed below the baseline floor.")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
