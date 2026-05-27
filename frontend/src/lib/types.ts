export type Message = {
  role: "user" | "assistant";
  content: string;
};

export type SourceChunk = {
  chunk_id: string;
  score: number;
  doc_id?: string | null;
  title?: string | null;
  section?: string | null;
  source?: string | null;
  authors?: string[] | null;
  year?: number | null;
  source_type?: string | null;
  url?: string | null;
  dense_score?: number | null;
  dense_score_norm?: number | null;
  bm25_score?: number | null;
  bm25_score_norm?: number | null;
  text: string;
};

export type TraceStep = {
  name: string;
  detail: string;
};

export type QueryResponse = {
  answer: string;
  sources: SourceChunk[];
  trace: TraceStep[];
};
