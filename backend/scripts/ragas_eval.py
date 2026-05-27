import argparse
import json
from pathlib import Path

from datasets import Dataset
from langchain_anthropic import ChatAnthropic
from langchain_community.embeddings import FastEmbedEmbeddings
from ragas import evaluate
from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

from app.core.config import settings
from app.services.agent import answer_question


def _load_samples(path: Path) -> list[dict[str, object]]:
    samples: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            question = payload.get("question")
            if not question:
                continue
            ground_truths = payload.get("ground_truths") or payload.get("ground_truth")
            if isinstance(ground_truths, str):
                ground_truths = [ground_truths]
            if not ground_truths:
                continue
            samples.append({"question": question, "ground_truths": ground_truths})
    return samples


def _build_dataset(samples: list[dict[str, object]], top_k: int) -> Dataset:
    questions: list[str] = []
    answers: list[str] = []
    contexts: list[list[str]] = []
    ground_truths: list[list[str]] = []

    for sample in samples:
        question = sample["question"]
        response = answer_question(question, top_k)
        questions.append(question)
        answers.append(response.answer)
        contexts.append([chunk.text for chunk in response.sources])
        ground_truths.append(sample["ground_truths"])

    return Dataset.from_dict(
        {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truths": ground_truths,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAGAS evaluation for Atlas RAG Studio")
    parser.add_argument("--data", type=str, required=True, help="Path to JSONL eval set")
    parser.add_argument("--top-k", type=int, default=5, help="Top-k retrieved chunks")
    parser.add_argument("--output", type=str, default="backend/data/ragas_report.csv")
    args = parser.parse_args()

    samples = _load_samples(Path(args.data))
    if not samples:
        raise SystemExit("No valid samples found in the eval file.")

    dataset = _build_dataset(samples, args.top_k)

    llm = ChatAnthropic(
        api_key=settings.anthropic_api_key,
        model=settings.anthropic_model,
        temperature=0,
    )
    embeddings = FastEmbedEmbeddings(model_name=settings.embedding_model)

    results = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=llm,
        embeddings=embeddings,
    )

    report_path = Path(args.output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_pandas().to_csv(report_path, index=False)

    print(results)
    print(f"Saved report to {report_path}")


if __name__ == "__main__":
    main()
