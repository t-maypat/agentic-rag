# Atlas RAG Studio

An agentic retrieval-augmented generation project designed as a portfolio-ready, production-minded demo for 2026. It includes a modern FastAPI backend, Pinecone vector search, Anthropic LLM orchestration, and a clean React interface for interactive exploration.

## Features
- Agentic query flow with retrieval planning, answer synthesis, and trace output
- Pinecone-backed semantic search with metadata-rich citations
- Hybrid search (vector + BM25) with configurable weighting
- Local ingestion pipeline for markdown, text, and JSON inputs
- Streaming-ready API design and modular services
- Frontend with sources, confidence signals, and run traces
- RAGAS evaluation script for retrieval/answer quality

## Quickstart
### Backend
1. Create a virtual environment and install dependencies
   - `python -m venv .venv`
   - `.venv\Scripts\activate`
   - `pip install -r backend\requirements.txt`
2. Copy env config and fill in keys
   - `copy backend\.env.example backend\.env`
3. Run the API
   - `uvicorn app.main:app --reload --app-dir backend`

### Frontend
1. Install dependencies
   - `cd frontend`
   - `npm install`
2. Configure API base URL
   - `copy .env.example .env`
3. Run the app
   - `npm run dev`

## Ingestion
Use the API to ingest local files or raw text payloads.
- POST `/ingest`
- POST `/query`

Sample documents are provided under `data/sample`.

Seed the index with the demo content:
- `python backend\scripts\seed_demo.py`

Run RAGAS evaluation:
- `python backend\scripts\ragas_eval.py --data path\to\eval.jsonl`

## Environment Variables
Backend:
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`
- `PINECONE_API_KEY`
- `PINECONE_INDEX`
- `PINECONE_CLOUD`
- `PINECONE_REGION`
- `EMBEDDING_MODEL`
- `EMBEDDING_DIM`

Frontend:
- `VITE_API_BASE_URL`

## Notes
This project is intended to be a clean, original implementation you can evolve into a fuller product demo.
