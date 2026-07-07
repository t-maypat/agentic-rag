"""Judged generation eval (nightly + manual, live APIs) — REVAMP_PLAN §8.3.

Runs the full graph in quick mode (real Pinecone + Gemini) over
``golden_generation.jsonl``, then a separate judge pass (gemini-2.5-flash, temp 0,
structured output) scores each item on faithfulness (1–5), key-fact coverage
(fraction of ``key_facts`` present), and correct-refusal (for unanswerable items).

Aggregates print to stdout; the full per-item report is written to
``eval_reports/<date>.json`` (gitignored) for the nightly workflow to upload.

This is NOT a merge gate (nondeterministic; judge and generator share a vendor —
see EVALS.md). A hard budget aborts the run after 150 LLM calls.

    uv run python scripts/run_generation_eval.py
"""

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.adapters.llm import GeminiLLM  # noqa: E402
from app.adapters.websearch import NullSearch  # noqa: E402
from app.agent import budget  # noqa: E402
from app.agent.deps import AgentDeps  # noqa: E402
from app.agent.graph import compile_graph  # noqa: E402
from app.agent.state import EvidenceChunk  # noqa: E402
from app.agent.tools import search_corpus  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.eval.datasets import load_golden_generation  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_GENERATION = REPO_ROOT / "data/eval/golden_generation.jsonl"
REPORT_DIR = REPO_ROOT / "eval_reports"

MAX_LLM_CALLS = 150  # hard budget for the whole run (§8.3)


class JudgeVerdict(BaseModel):
    faithfulness: int = Field(ge=1, le=5)
    covered_key_facts: list[bool] = Field(default_factory=list)
    correct_refusal: bool = False
    note: str = ""


_JUDGE_SYSTEM = (
    "You are a strict evaluator of a retrieval-augmented research assistant. "
    "Judge only against the retrieved evidence provided; never use outside knowledge."
)


def _evidence_block(sources: list[EvidenceChunk]) -> str:
    if not sources:
        return "(no evidence retrieved)"
    blocks = []
    for chunk in sources:
        label = chunk.source_id or chunk.id
        blocks.append(f"[{label}] {chunk.doc_title}\n{chunk.text}")
    return "\n\n".join(blocks)


def _judge_prompt(item: dict[str, Any], answer_md: str, outcome: str, evidence: str) -> str:
    key_facts = item.get("key_facts") or []
    facts_lines = "\n".join(f"- {fact}" for fact in key_facts) or "(none)"
    return (
        f"QUESTION:\n{item['question']}\n\n"
        f"ANSWERABLE FROM CORPUS: {item['answerable']}\n"
        f"GENERATOR OUTCOME: {outcome}\n\n"
        f"ANSWER UNDER REVIEW:\n{answer_md or '(the assistant refused to answer)'}\n\n"
        f"RETRIEVED EVIDENCE:\n{evidence}\n\n"
        f"KEY FACTS THAT SHOULD APPEAR (in order):\n{facts_lines}\n\n"
        "Return JSON with:\n"
        "- faithfulness: 1-5, how well the answer's claims are supported by the retrieved "
        "evidence (5 = every claim supported; 1 = mostly unsupported/hallucinated). For a "
        "correct refusal on an unanswerable question, use 5.\n"
        "- covered_key_facts: a list of booleans, one per key fact above in order, true if the "
        "answer conveys that fact. Empty list if there are no key facts.\n"
        "- correct_refusal: true if the question is NOT answerable from the corpus and the "
        "answer appropriately declines/refuses instead of fabricating; otherwise false.\n"
        "- note: one short sentence of justification."
    )


def _run_generator(graph: Any, deps: AgentDeps, question: str) -> dict[str, Any]:
    config = {"configurable": {"deps": deps}}
    final = graph.invoke({"question": question, "mode": "quick"}, config)
    return final


def main() -> int:
    if not settings.gemini_api_key:
        raise SystemExit("GEMINI_API_KEY is required for the generation eval.")

    llm = GeminiLLM(settings.gemini_api_key)
    deps = AgentDeps(llm=llm, search_corpus=search_corpus, search_web=NullSearch())
    graph = compile_graph(checkpointer=None)

    items = load_golden_generation(GOLDEN_GENERATION)
    results: list[dict[str, Any]] = []
    total_calls = 0

    for item in items:
        if total_calls >= MAX_LLM_CALLS:
            print(f"Budget reached ({total_calls} LLM calls); stopping early.")
            break

        final = _run_generator(graph, deps, item["question"])
        answer_md = final.get("draft_answer") or ""
        outcome = final.get("outcome") or "unknown"
        sources = final.get("sources") or []
        gen_calls = final["ledger"].llm_calls
        total_calls += gen_calls

        judge_ledger = budget.new_ledger()
        verdict = llm.generate_json(
            _judge_prompt(item, answer_md, outcome, _evidence_block(sources)),
            JudgeVerdict,
            ledger=judge_ledger,
            system=_JUDGE_SYSTEM,
            role="synth",
            temperature=0.0,
            prompt_id="generation_judge",
        )
        total_calls += judge_ledger.llm_calls

        key_facts = item.get("key_facts") or []
        covered = verdict.covered_key_facts[: len(key_facts)]
        coverage = (sum(1 for c in covered if c) / len(key_facts)) if key_facts else None

        results.append(
            {
                "qid": item["qid"],
                "answerable": item["answerable"],
                "outcome": outcome,
                "faithfulness": verdict.faithfulness,
                "key_fact_coverage": coverage,
                "correct_refusal": verdict.correct_refusal,
                "note": verdict.note,
            }
        )
        cov_str = f"{coverage:.2f}" if coverage is not None else "n/a"
        print(
            f"  {item['qid']:<8} outcome={outcome:<11} "
            f"faith={verdict.faithfulness} cov={cov_str}"
        )

    answerable = [r for r in results if r["answerable"]]
    unanswerable = [r for r in results if not r["answerable"]]

    def _mean(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    summary = {
        "n_items": len(results),
        "n_answerable": len(answerable),
        "n_unanswerable": len(unanswerable),
        "mean_faithfulness": _mean([r["faithfulness"] for r in answerable]),
        "mean_key_fact_coverage": _mean(
            [r["key_fact_coverage"] for r in answerable if r["key_fact_coverage"] is not None]
        ),
        "correct_refusal_rate": _mean([1.0 if r["correct_refusal"] else 0.0 for r in unanswerable]),
        "total_llm_calls": total_calls,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    date = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d")
    report_path = REPORT_DIR / f"{date}.json"
    report_path.write_text(
        json.dumps({"summary": summary, "items": results}, indent=2) + "\n", encoding="utf-8"
    )

    print("\nGeneration eval summary")
    for name, value in summary.items():
        printable = f"{value:.3f}" if isinstance(value, float) else value
        print(f"  {name}: {printable}")
    print(f"\nWrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
