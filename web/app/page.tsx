"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getStats,
  postQuery,
  type QueryMode,
  type QueryResult,
  type StatsResult,
} from "@/lib/api";

export default function Home() {
  const [question, setQuestion] = useState("");
  const [site, setSite] = useState("");
  const [mode, setMode] = useState<QueryMode>("hybrid");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [stats, setStats] = useState<StatsResult | null>(null);

  const loadStats = useCallback(async () => {
    try {
      setStats(await getStats());
    } catch {
      setStats(null);
    }
  }, []);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const r = await postQuery({
        question,
        mode,
        site: site.trim() || undefined,
      });
      setResult(r);
      loadStats();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-5 py-12 md:py-16">
      <header className="mb-12 text-center">
        <p className="mb-2 text-xs font-medium tracking-[0.2em] text-muted">
          SharePoint × Gemini
        </p>
        <h1 className="text-2xl font-semibold tracking-tight text-ink md:text-3xl">
          社内文書検索
        </h1>
        <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-muted">
          ハイブリッド（Microsoft Search）とベクトル RAG から選択して質問できます。
        </p>
      </header>

      {stats && (
        <div className="mb-8 rounded-lg border border-line bg-card/80 px-4 py-3 text-center text-xs text-muted shadow-soft backdrop-blur-sm">
          インデックス:{" "}
          <span className="font-medium text-ink">{stats.total_files}</span>{" "}
          ファイル /{" "}
          <span className="font-medium text-ink">{stats.total_chunks}</span>{" "}
          チャンク（RAG 利用時）
        </div>
      )}

      <form
        onSubmit={onSubmit}
        className="rounded-2xl border border-line bg-card p-6 shadow-soft md:p-8"
      >
        <div className="mb-6 flex flex-wrap gap-2">
          <span className="w-full text-xs font-medium text-muted">検索モード</span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setMode("hybrid")}
              className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                mode === "hybrid"
                  ? "bg-accent text-white shadow-sm"
                  : "bg-wash text-muted hover:bg-line/80"
              }`}
            >
              ハイブリッド
            </button>
            <button
              type="button"
              onClick={() => setMode("rag")}
              className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                mode === "rag"
                  ? "bg-accent text-white shadow-sm"
                  : "bg-wash text-muted hover:bg-line/80"
              }`}
            >
              ベクトル RAG
            </button>
          </div>
          <p className="mt-2 w-full text-[11px] leading-relaxed text-muted">
            {mode === "hybrid"
              ? "検索インデックスから上位ファイルのみ取得（全件インデックス不要）"
              : "事前の index 済みチャンクを類似度検索（ベクトル DB）"}
          </p>
        </div>

        <label className="mb-4 block">
          <span className="mb-1.5 block text-xs font-medium text-muted">
            サイト（任意）
          </span>
          <input
            type="text"
            value={site}
            onChange={(e) => setSite(e.target.value)}
            placeholder="例: eco-action"
            className="w-full rounded-lg border border-line bg-white px-3 py-2.5 text-sm text-ink placeholder:text-muted/70 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
          />
        </label>

        <label className="mb-6 block">
          <span className="mb-1.5 block text-xs font-medium text-muted">
            質問
          </span>
          <textarea
            required
            rows={4}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="例: 4月の請求書の内容を要約してください"
            className="w-full resize-y rounded-lg border border-line bg-white px-3 py-2.5 text-sm leading-relaxed text-ink placeholder:text-muted/70 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
          />
        </label>

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-xl bg-accent py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-accent-hover disabled:opacity-60"
        >
          {loading ? "回答を生成しています…" : "質問する"}
        </button>
      </form>

      {error && (
        <div className="mt-6 rounded-xl border border-red-200 bg-red-50/90 px-4 py-3 text-sm text-red-900">
          {error}
        </div>
      )}

      {result && (
        <section className="mt-10">
          <h2 className="mb-3 text-sm font-semibold text-ink">回答</h2>
          <div className="rounded-2xl border border-line bg-card p-6 shadow-soft">
            <div className="whitespace-pre-wrap text-sm leading-[1.85] text-ink">
              {result.answer}
            </div>
          </div>

          <h3 className="mb-2 mt-8 text-xs font-medium tracking-wide text-muted">
            参照資料（{result.retrieved_count} 件）
          </h3>
          <ul className="space-y-2">
            {result.sources.length === 0 ? (
              <li className="text-sm text-muted">なし</li>
            ) : (
              result.sources.map((s, i) => (
                <li
                  key={`${s.name}-${i}`}
                  className="rounded-lg border border-line/80 bg-white/90 px-3 py-2.5 text-sm"
                >
                  <span className="font-medium text-ink">{s.name}</span>
                  {s.site ? (
                    <span className="ml-2 text-xs text-muted">[{s.site}]</span>
                  ) : null}
                  {s.similarity != null ? (
                    <span className="ml-2 text-xs text-muted">
                      関連度: {(s.similarity * 100).toFixed(1)}%
                    </span>
                  ) : null}
                  {s.rank != null ? (
                    <span className="ml-2 text-xs text-muted">
                      検索順位: {s.rank}
                    </span>
                  ) : null}
                  {s.web_url ? (
                    <a
                      href={s.web_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-1 block truncate text-xs text-accent underline-offset-2 hover:underline"
                    >
                      {s.web_url}
                    </a>
                  ) : null}
                </li>
              ))
            )}
          </ul>
        </section>
      )}

      <footer className="mt-16 border-t border-line pt-8 text-center text-[11px] text-muted">
        API:{" "}
        <code className="rounded bg-line/60 px-1.5 py-0.5">
          {process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}
        </code>
      </footer>
    </div>
  );
}
