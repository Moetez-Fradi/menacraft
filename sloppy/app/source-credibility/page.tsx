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

const PAGE_COPY = {
  headerTitle: "Evaluate source credibility",
  headerSubtitle:
    "Estimate how trustworthy a source is using account history and link quality signals.",
  requestTitle: "1) Enter source details",
  requestSubtitle:
    "Provide account metrics and optional post text/links. We use these fields to calculate risk.",
  resultTitle: "2) Credibility result",
  resultSubtitle:
    "Review the score, risk level, and key flags identified by the credibility model.",
  advancedTitle: "Advanced technical output",
  advancedSubtitle:
    "Raw service payload for troubleshooting and engineering use.",
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
    <main className="app-page">
      <header className="app-header panel p-5 md:p-6">
        <span className="endpoint-kicker">Source credibility</span>
        <h1 className="app-title">{PAGE_COPY.headerTitle}</h1>
        <p className="app-subtitle">{PAGE_COPY.headerSubtitle}</p>
      </header>

      <section className="panel p-5 md:p-6">
        <div className="mb-4 space-y-1">
          <h2 className="section-title">{PAGE_COPY.requestTitle}</h2>
          <p className="section-description">{PAGE_COPY.requestSubtitle}</p>
        </div>

        <form className="space-y-5" onSubmit={onSubmit}>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="form-label">
              Account username
              <input
                className="input-control"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="news_bot_99"
                required
              />
            </label>
            <label className="form-label">
              Platform
              <select
                className="input-control"
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
            <label className="form-label">
              Account age (days)
              <input
                className="input-control"
                type="number"
                min={0}
                value={accountAgeDays}
                onChange={(event) => setAccountAgeDays(event.target.value)}
                required
              />
            </label>
            <label className="form-label">
              Followers
              <input
                className="input-control"
                type="number"
                min={0}
                value={followers}
                onChange={(event) => setFollowers(event.target.value)}
                required
              />
            </label>
            <label className="form-label">
              Following
              <input
                className="input-control"
                type="number"
                min={0}
                value={following}
                onChange={(event) => setFollowing(event.target.value)}
                required
              />
            </label>
            <label className="form-label">
              Total posts
              <input
                className="input-control"
                type="number"
                min={0}
                value={postsCount}
                onChange={(event) => setPostsCount(event.target.value)}
                required
              />
            </label>
          </div>

          <label className="form-label">
            Optional timestamp
            <input
              className="input-control"
              value={timestamp}
              onChange={(event) => setTimestamp(event.target.value)}
              placeholder="2026-04-04T12:00:00Z"
            />
          </label>

          <label className="form-label">
            Optional text sample
            <textarea
              className="input-control min-h-28"
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Post text or article excerpt"
            />
          </label>

          <label className="form-label">
            Optional links (comma or newline separated)
            <textarea
              className="input-control min-h-20"
              value={linksInput}
              onChange={(event) => setLinksInput(event.target.value)}
              placeholder="https://example.com/story"
            />
          </label>

          <button
            className="primary-btn"
            disabled={loading}
            type="submit"
          >
            {loading ? "Running..." : "Evaluate credibility"}
          </button>
        </form>
      </section>

      {error ? (
        <section className="alert-error">
          {error}
        </section>
      ) : null}

      {result ? (
        <section className="grid gap-4 md:grid-cols-2">
          <article className="panel p-5">
            <h2 className="section-title">{PAGE_COPY.resultTitle}</h2>
            <p className="section-description mb-3">{PAGE_COPY.resultSubtitle}</p>
            <div className="mb-3 flex flex-wrap gap-2">
              <span className="stat-chip">
                Score: {result.credibility_score ?? "n/a"}
              </span>
              <span className="stat-chip">
                Risk: {result.risk_level ?? "n/a"}
              </span>
            </div>
            <div className="space-y-2 text-sm">
              <p><strong>Explanation:</strong> {result.explanation ?? ""}</p>
            </div>
            <pre className="code-block">
              {JSON.stringify({ flags: result.flags }, null, 2)}
            </pre>
          </article>

          <article className="panel p-5">
            <h2 className="section-title">{PAGE_COPY.advancedTitle}</h2>
            <p className="section-description mb-3">{PAGE_COPY.advancedSubtitle}</p>
            <details>
              <summary className="cursor-pointer text-sm font-medium text-violet-700 dark:text-violet-300">
                Show advanced JSON
              </summary>
              <pre className="code-block max-h-[32rem]">
                {JSON.stringify({ service: result.service }, null, 2)}
              </pre>
            </details>
          </article>
        </section>
      ) : null}
    </main>
  );
}
