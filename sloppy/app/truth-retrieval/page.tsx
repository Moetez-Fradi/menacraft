"use client";

import { FormEvent, useState } from "react";

type TruthRetrievalResponse = {
  is_news?: boolean;
  is_misinformation?: boolean;
  confidence?: number;
  verdict?: string;
  explanation?: string;
  corrected_version?: string;
  sources?: unknown[];
  service?: unknown;
  error?: string;
};

export default function TruthRetrievalPage() {
  const [sessionId, setSessionId] = useState(`manual-${Date.now()}`);
  const [cleanText, setCleanText] = useState("");
  const [contentType, setContentType] = useState("text");
  const [metadataJson, setMetadataJson] = useState("{}");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<TruthRetrievalResponse | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const metadata = JSON.parse(metadataJson) as Record<string, unknown>;
      const response = await fetch("/api/truth-retrieval", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          clean_text: cleanText,
          content_type: contentType,
          metadata,
        }),
      });

      const body = (await response.json()) as TruthRetrievalResponse;
      if (!response.ok) {
        throw new Error(body.error || `Request failed (${response.status})`);
      }
      setResult(body);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Unexpected error while calling truth retrieval service",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-4 py-8 md:px-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Truth Retrieval Endpoint: /truth</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-300">
          Verify claim text against external sources and inspect verdict confidence.
        </p>
      </header>

      <section className="rounded-lg border border-zinc-300 p-4 dark:border-zinc-700">
        <form className="space-y-4" onSubmit={onSubmit}>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm">
              Session ID
              <input
                className="rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
                value={sessionId}
                onChange={(event) => setSessionId(event.target.value)}
                required
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Content Type
              <select
                className="rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
                value={contentType}
                onChange={(event) => setContentType(event.target.value)}
              >
                <option value="text">text</option>
                <option value="post">post</option>
                <option value="image">image</option>
                <option value="video">video</option>
              </select>
            </label>
          </div>

          <label className="flex flex-col gap-1 text-sm">
            Clean Text
            <textarea
              className="min-h-32 rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
              value={cleanText}
              onChange={(event) => setCleanText(event.target.value)}
              placeholder="Claim text to verify"
              required
            />
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Metadata (JSON)
            <textarea
              className="min-h-24 rounded border border-zinc-300 bg-transparent px-3 py-2 font-mono text-xs dark:border-zinc-700"
              value={metadataJson}
              onChange={(event) => setMetadataJson(event.target.value)}
            />
          </label>

          <button
            className="rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
            disabled={loading}
            type="submit"
          >
            {loading ? "Running..." : "Run /truth"}
          </button>
        </form>
      </section>

      {error ? (
        <section className="rounded-lg border border-red-400 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
          {error}
        </section>
      ) : null}

      {result ? (
        <section className="grid gap-4 md:grid-cols-2">
          <article className="rounded-lg border border-zinc-300 p-4 dark:border-zinc-700">
            <h2 className="mb-2 text-base font-semibold">Truth Verification Summary</h2>
            <div className="space-y-2 text-sm">
              <p><strong>Verdict:</strong> {result.verdict ?? "n/a"}</p>
              <p><strong>Confidence:</strong> {result.confidence ?? "n/a"}</p>
              <p><strong>Is News:</strong> {String(result.is_news ?? false)}</p>
              <p><strong>Is Misinformation:</strong> {String(result.is_misinformation ?? false)}</p>
              <p><strong>Explanation:</strong> {result.explanation ?? ""}</p>
            </div>
            <pre className="mt-3 max-h-[24rem] overflow-auto text-xs">
              {JSON.stringify(
                {
                  corrected_version: result.corrected_version,
                  sources: result.sources,
                },
                null,
                2,
              )}
            </pre>
          </article>

          <article className="rounded-lg border border-zinc-300 p-4 dark:border-zinc-700">
            <h2 className="mb-2 text-base font-semibold">Debug Trace</h2>
            <pre className="max-h-[28rem] overflow-auto text-xs">
              {JSON.stringify({ service: result.service }, null, 2)}
            </pre>
          </article>
        </section>
      ) : null}
    </main>
  );
}
