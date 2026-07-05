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
   - `cd backend`
   - `uv venv`
   - `uv pip install -r requirements.txt`
2. Create `backend/.env` from `backend/.env.example` and fill in required keys.
3. Run the API
   - `uvicorn app.main:app --reload`

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
  - `cd backend`
  - `uv run scripts\seed_corpus.py`

## Evaluation
- Run batch RAGAS evaluation with a JSONL dataset:
  - `python backend\scripts\ragas_eval.py --data path\to\eval.jsonl`
- Output is saved to backend/data/ragas_report.csv.
- Starter eval set: data/eval/ai_research_eval.jsonl

## Environment Variables
Backend:
- `GEMINI_API_KEY`
- `APP_ENV`
- `LLM_PROVIDER` (default: gemini)
- `LLM_MODEL` (default: gemini-1.5-pro)
- `EMBEDDING_PROVIDER` (default: gemini)
- `EMBEDDING_MODEL` (default: gemini-embedding-001)
- `EMBEDDING_DIM` (default: 768)
- `EMBEDDING_BATCH_SIZE`
- `PINECONE_API_KEY`
- `PINECONE_INDEX`
- `PINECONE_CLOUD`
- `PINECONE_REGION`
- `PUBLIC_INGEST_ENABLED`
- `REQUIRE_HCAPTCHA`
- `HCAPTCHA_SECRET_KEY`
- `HCAPTCHA_SITE_KEY`
- `QUERY_MAX_CHARS`
- `QUERY_TOP_K_MAX`
- `RATE_LIMIT_WINDOW_SECONDS`
- `RATE_LIMIT_REQUESTS_PER_WINDOW`
- `DAILY_REQUEST_LIMIT`
- `CACHE_TTL_SECONDS`
- `SESSION_SIGNING_SECRET`
- `HYBRID_SEARCH_ENABLED`
- `HYBRID_ALPHA`
- `BM25_K`
- `LEXICAL_INDEX_PATH`

Frontend:
- `VITE_API_BASE_URL`
- `VITE_HCAPTCHA_SITE_KEY`

## Deployment
Recommended free-tier stack:
- Frontend: Vercel Hobby
- Backend: Render free web service
- Bot protection: hCaptcha
- Dense retrieval: Pinecone Starter
- LLM and embeddings: Gemini API free tier

Production checklist:
1. Deploy the backend with `APP_ENV=production`.
2. Set `PUBLIC_INGEST_ENABLED=false`.
3. Set `REQUIRE_HCAPTCHA=true`.
4. Configure `HCAPTCHA_SECRET_KEY` on the backend and `VITE_HCAPTCHA_SITE_KEY` on the frontend.
5. Set `CORS_ORIGINS` to the deployed frontend domain.
6. Rotate any Gemini or Pinecone keys that were exposed during local development.


## Project Status & Limitations
**Note:** While designed as a portfolio piece, the current system is purely a **Hybrid RAG** implementation. Currently, it does not use true autonomous agent workflows (e.g., LangGraph, ReAct loops, or dynamic tool use) despite the initial project naming. Future iterations will pivot to incorporate LangGraph/LlamaIndex for advanced query routing and iterative research.

## Engineering Roadmap (Local)
This repo includes a local-only roadmap in plan.md with the LangGraph node graph and performance refactor plan. It is gitignored by design.
