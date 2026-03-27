const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type QueryMode = "hybrid" | "rag";

export type SourceItem = {
  name: string;
  path?: string;
  site?: string;
  similarity?: number | null;
  rank?: number | null;
  web_url?: string;
};

export type QueryResult = {
  question: string;
  answer: string;
  retrieved_count: number;
  sources: SourceItem[];
  mode: QueryMode;
};

export type StatsResult = {
  total_files: number;
  total_chunks: number;
  by_site: Record<string, number>;
  vector_collections: Record<string, number>;
};

export async function postQuery(body: {
  question: string;
  mode: QueryMode;
  site?: string | null;
  top_k?: number;
  hybrid_top?: number;
}): Promise<QueryResult> {
  const res = await fetch(`${API_BASE}/api/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: body.question,
      mode: body.mode,
      site: body.site || null,
      top_k: body.top_k,
      hybrid_top: body.hybrid_top,
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getStats(): Promise<StatsResult> {
  const res = await fetch(`${API_BASE}/api/stats`, { cache: "no-store" });
  if (!res.ok) throw new Error(`stats: ${res.status}`);
  return res.json();
}
