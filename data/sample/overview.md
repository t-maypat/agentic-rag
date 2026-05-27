This project demonstrates agentic retrieval-augmented generation. It combines a FastAPI backend with a Pinecone vector index, a local embedding model, and an Anthropic model for synthesis.

Project goals:
- Fast ingestion of markdown and JSON documents
- Reliable citations using metadata from the vector store
- Clear traces that show how each answer was produced
- Hybrid retrieval that blends vector similarity with lexical relevance

High-level architecture:
- API layer: FastAPI routes for ingest and query
- Retrieval layer: Pinecone vector search plus optional BM25 lexical search
- Orchestration: Agent step traces for retrieve -> synthesize
- Frontend: React UI that shows sources and trace steps

Retrieval behavior:
- Vector search uses dense embeddings for semantic coverage
- Lexical BM25 search adds exact keyword matching for precision
- Hybrid scoring blends vector and BM25 scores to improve recall

Operational notes:
- Embedding model runs locally to control latency and cost
- Pinecone is used for low-latency vector queries
- Response format is bullet-based with inline citations

Known limitations:
- No multi-tenant auth or access control
- No active learning loop to improve retrieval over time
- Evaluation is offline only (RAGAS script)
