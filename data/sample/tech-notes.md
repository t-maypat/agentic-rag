Retrieval:
- Dense embeddings generated locally to keep costs low and latency predictable.
- Pinecone stores vectors with chunk-level metadata, including title and source path.
- Lexical BM25 index stored as JSONL for local fallback and hybrid search.

Chunking:
- Simple char-based splitter with overlap to preserve context.
- Chunk metadata includes doc_id, chunk_index, title, and source path.

Synthesis:
- Short bullet points with citations in [n] format.
- Explicitly calls out missing evidence when sources are insufficient.

Hybrid scoring:
- Vector scores normalized per query.
- BM25 scores normalized by max BM25 score in the result set.
- Hybrid score = alpha * vector + (1 - alpha) * lexical.

Evaluation:
- Offline RAGAS script for faithfulness, answer relevancy, context precision, and context recall.
- Eval data uses JSONL with question and ground_truths fields.

Configuration knobs:
- hybrid_search_enabled (bool)
- hybrid_alpha (float)
- bm25_k (int)
- max_chunk_chars and chunk_overlap
