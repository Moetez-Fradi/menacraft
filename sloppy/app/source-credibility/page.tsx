"use client";

import { FormEvent, useState } from "react";

type SourceCredibilityResponse = {
  credibility_score?: number;
  risk_level?: string;
  flags?: string[];
  explanation?: string;
  service?: unknown;
  error?: string;
};

export default function SourceCredibilityPage() {
  const [text, setText] = useState("");
  const [username, setUsername] = useState("");
  const [accountAgeDays, setAccountAgeDays] = useState("30");
  const [followers, setFollowers] = useState("100");
  const [following, setFollowing] = useState("100");
  const [postsCount, setPostsCount] = useState("20");
  const [platform, setPlatform] = useState("web");
  const [timestamp, setTimestamp] = useState("");
  const [linksInput, setLinksInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<SourceCredibilityResponse | null>(null);

  function parseLinks(raw: string): string[] {
    return raw
      .split(/\n|,/g)
      .map((item) => item.trim())
      .filter((item) => item.length > 0);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch("/api/source-credibility", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          author: {
            username,
            account_age_days: Number(accountAgeDays),
            followers: Number(followers),
            following: Number(following),
            posts_count: Number(postsCount),
          },
          content_metadata: {
            platform,
            ...(timestamp ? { timestamp } : {}),
          },
          links: parseLinks(linksInput),
        }),
      });

      const body = (await response.json()) as SourceCredibilityResponse;
      if (!response.ok) {
        throw new Error(body.error || `Request failed (${response.status})`);
      }
      setResult(body);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Unexpected error while calling source credibility service",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-4 py-8 md:px-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Source Credibility Endpoint: /analyze</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-300">
          Evaluate account and link trust signals for credibility scoring.
        </p>
      </header>

      <section className="rounded-lg border border-zinc-300 p-4 dark:border-zinc-700">
        <form className="space-y-4" onSubmit={onSubmit}>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm">
              Username
              <input
                className="rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="news_bot_99"
                required
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Platform
              <select
                className="rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
                value={platform}
                onChange={(event) => setPlatform(event.target.value)}
              >
                <option value="web">web</option>
                <option value="twitter">twitter</option>
                <option value="facebook">facebook</option>
                <option value="instagram">instagram</option>
                <option value="linkedin">linkedin</option>
                <option value="reddit">reddit</option>
                <option value="youtube">youtube</option>
                <option value="tiktok">tiktok</option>
              </select>
            </label>
          </div>

          <div className="grid gap-4 md:grid-cols-4">
            <label className="flex flex-col gap-1 text-sm">
              Account Age (days)
              <input
                className="rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
                type="number"
                min={0}
                value={accountAgeDays}
                onChange={(event) => setAccountAgeDays(event.target.value)}
                required
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Followers
              <input
                className="rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
                type="number"
                min={0}
                value={followers}
                onChange={(event) => setFollowers(event.target.value)}
                required
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Following
              <input
                className="rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
                type="number"
                min={0}
                value={following}
                onChange={(event) => setFollowing(event.target.value)}
                required
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Posts Count
              <input
                className="rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
                type="number"
                min={0}
                value={postsCount}
                onChange={(event) => setPostsCount(event.target.value)}
                required
              />
            </label>
          </div>

          <label className="flex flex-col gap-1 text-sm">
            Timestamp (optional)
            <input
              className="rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
              value={timestamp}
              onChange={(event) => setTimestamp(event.target.value)}
              placeholder="2026-04-04T12:00:00Z"
            />
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Text
            <textarea
              className="min-h-28 rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Post text or article excerpt"
            />
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Links (comma or newline separated)
            <textarea
              className="min-h-20 rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
              value={linksInput}
              onChange={(event) => setLinksInput(event.target.value)}
              placeholder="https://example.com/story"
            />
          </label>

          <button
            className="rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
            disabled={loading}
            type="submit"
          >
            {loading ? "Running..." : "Run /analyze"}
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
            <h2 className="mb-2 text-base font-semibold">Credibility Summary</h2>
            <div className="space-y-2 text-sm">
              <p><strong>Credibility Score:</strong> {result.credibility_score ?? "n/a"}</p>
              <p><strong>Risk Level:</strong> {result.risk_level ?? "n/a"}</p>
              <p><strong>Explanation:</strong> {result.explanation ?? ""}</p>
            </div>
            <pre className="mt-3 max-h-[24rem] overflow-auto text-xs">
              {JSON.stringify({ flags: result.flags }, null, 2)}
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
