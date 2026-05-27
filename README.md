# Research RAG Studio

Research RAG Studio is an AI research assistant that delivers grounded answers over a curated corpus of LLM, RAG, and retrieval literature. It combines hybrid retrieval, traceable reasoning steps, and Gemini-backed synthesis in a clean, modular architecture.

## What it solves
- Research teams need fast, cited answers across papers, benchmarks, and technical guidance.
- RAG systems need transparent retrieval diagnostics and reproducible evaluation.

## Corpus
- Curated set of 30+ seminal papers, benchmarks, and high-signal technical docs.
- Stored in data/corpus/ai_research_corpus.json with rich metadata (title, authors, year, section, source type, URL).

## Retrieval approach
- Dense retrieval via Pinecone with Gemini embeddings.
- Local BM25 index for lexical precision.
- Normalized score fusion with configurable alpha and traceable ranking.

## Architecture overview
- backend/app/services: ingestion, chunking, retrieval, providers, orchestration.
- backend/app/api/routes: health, ingest, query endpoints.
- frontend/src: research assistant UI with sources and trace panel.

## Quickstart
### Backend
1. Create a virtual environment and install dependencies
   - `python -m venv .venv`
   - `.venv\Scripts\activate`
   - `pip install -r backend\requirements.txt`
2. Create backend/.env with required keys (see Environment Variables).
3. Run the API
   - `uvicorn app.main:app --reload --app-dir backend`

### Frontend
1. Install dependencies
   - `cd frontend`
   - `npm install`
2. Configure API base URL in frontend/.env
   - `VITE_API_BASE_URL=http://localhost:8000`
3. Run the app
   - `npm run dev`

## Ingestion
- POST `/ingest` for local paths or inline documents.
- Seed the curated corpus:
  - `python backend\scripts\seed_corpus.py`

## Evaluation
- Run batch RAGAS evaluation with a JSONL dataset:
  - `python backend\scripts\ragas_eval.py --data path\to\eval.jsonl`
- Output is saved to backend/data/ragas_report.csv.
- Starter eval set: data/eval/ai_research_eval.jsonl

## Environment Variables
Backend:
- `GEMINI_API_KEY`
- `LLM_PROVIDER` (default: gemini)
- `LLM_MODEL` (default: gemini-1.5-pro)
- `EMBEDDING_PROVIDER` (default: gemini)
- `EMBEDDING_MODEL` (default: models/text-embedding-004)
- `EMBEDDING_DIM` (default: 768)
- `PINECONE_API_KEY`
- `PINECONE_INDEX`
- `PINECONE_CLOUD`
- `PINECONE_REGION`
- `HYBRID_SEARCH_ENABLED`
- `HYBRID_ALPHA`
- `BM25_K`
- `LEXICAL_INDEX_PATH`

Frontend:
- `VITE_API_BASE_URL`
