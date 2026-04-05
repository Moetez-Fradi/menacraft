"use client";

import { ChangeEvent, FormEvent, useState } from "react";

type AnalyzeResponse = {
  case_id?: string;
  explainability?: {
    explanation?: string;
    verdict?: string;
    scores?: unknown;
    evidence?: unknown[];
    suspicious_parts?: unknown[];
    suspicious_timestamps?: unknown[];
    debug?: unknown;
    traces?: unknown[];
  };
  raw_report?: unknown;
  error?: string;
};

export default function AnalyzePage() {
  const [sessionId, setSessionId] = useState(`manual-${Date.now()}`);
  const [text, setText] = useState("");
  const [contentType, setContentType] = useState("text");
  const [platform, setPlatform] = useState("web");
  const [linksInput, setLinksInput] = useState("");
  const [extraMetadataJson, setExtraMetadataJson] = useState("{}");
  const [imageBase64, setImageBase64] = useState("");
  const [selectedFileName, setSelectedFileName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<AnalyzeResponse | null>(null);

  function parseLinks(raw: string): string[] {
    return raw
      .split(/\n|,/g)
      .map((item) => item.trim())
      .filter((item) => item.length > 0);
  }

  function toBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const value = String(reader.result ?? "");
        const b64 = value.includes(",") ? value.split(",")[1] : "";
        resolve(b64);
      };
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
  }

  async function extractVideoFrame(file: File): Promise<string> {
    const objectUrl = URL.createObjectURL(file);
    try {
      const video = document.createElement("video");
      video.src = objectUrl;
      video.muted = true;
      video.playsInline = true;

      await new Promise<void>((resolve, reject) => {
        video.onloadeddata = () => resolve();
        video.onerror = () => reject(new Error("Unable to read video file"));
      });

      const width = Math.min(video.videoWidth || 320, 640);
      const height = Math.min(video.videoHeight || 180, 360);
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");

      if (!ctx) {
        throw new Error("Canvas context is unavailable");
      }

      ctx.drawImage(video, 0, 0, width, height);
      const dataUrl = canvas.toDataURL("image/jpeg", 0.8);
      return dataUrl.split(",")[1] || "";
    } finally {
      URL.revokeObjectURL(objectUrl);
    }
  }

  async function handleFileInput(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setSelectedFileName(file.name);
    setError("");

    try {
      if (contentType === "video") {
        const frame = await extractVideoFrame(file);
        setImageBase64(frame);
        return;
      }

      const b64 = await toBase64(file);
      setImageBase64(b64);
    } catch (fileError) {
      setError(
        fileError instanceof Error
          ? fileError.message
          : "Failed to process file",
      );
      setImageBase64("");
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const extraMetadata = JSON.parse(extraMetadataJson) as Record<string, unknown>;
      const links = parseLinks(linksInput);
      const metadata: Record<string, unknown> = {
        platform,
        ...(links.length ? { links } : {}),
        ...extraMetadata,
      };

      const response = await fetch("/api/classifier/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          text,
          image_base64: imageBase64,
          content_type: contentType,
          metadata,
        }),
      });

      const body = (await response.json()) as AnalyzeResponse;
      if (!response.ok) {
        throw new Error(body.error || `Request failed (${response.status})`);
      }
      setResult(body);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Unexpected error while calling /v1/analyze",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-4 py-8 md:px-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Classifier Endpoint: /v1/analyze</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-300">
          Submit case input and inspect explainability from the generated report.
        </p>
      </header>

      <section className="rounded-lg border border-zinc-300 p-4 dark:border-zinc-700">
        <form className="space-y-4" onSubmit={onSubmit}>
          <div className="grid gap-4 md:grid-cols-3">
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
                <option value="image">image</option>
                <option value="video">video</option>
                <option value="post">post</option>
                <option value="audio">audio</option>
                <option value="document">document</option>
              </select>
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

          <label className="flex flex-col gap-1 text-sm">
            Text
            <textarea
              className="min-h-32 rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Claim or post text"
            />
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Links (comma or newline separated)
            <textarea
              className="min-h-20 rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
              value={linksInput}
              onChange={(event) => setLinksInput(event.target.value)}
              placeholder="https://example.com/news-1"
            />
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Upload media (optional)
            <input
              className="rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
              type="file"
              accept={
                contentType === "video"
                  ? "video/*"
                  : contentType === "audio"
                    ? "audio/*"
                    : contentType === "document"
                      ? ".txt,.pdf,.doc,.docx"
                      : "image/*"
              }
              onChange={handleFileInput}
            />
            <span className="text-xs text-zinc-500 dark:text-zinc-400">
              {selectedFileName
                ? `Loaded: ${selectedFileName}`
                : "For video, the first frame is extracted and sent as image_base64."}
            </span>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Extra Metadata (JSON)
            <textarea
              className="min-h-24 rounded border border-zinc-300 bg-transparent px-3 py-2 font-mono text-xs dark:border-zinc-700"
              value={extraMetadataJson}
              onChange={(event) => setExtraMetadataJson(event.target.value)}
            />
          </label>

          <button
            className="rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
            disabled={loading}
            type="submit"
          >
            {loading ? "Running..." : "Run /v1/analyze"}
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
            <h2 className="mb-2 text-base font-semibold">Explainability Summary</h2>
            <div className="space-y-2 text-sm">
              <p><strong>Case ID:</strong> {result.case_id ?? "n/a"}</p>
              <p><strong>Verdict:</strong> {result.explainability?.verdict ?? "n/a"}</p>
              <p><strong>Explanation:</strong> {result.explainability?.explanation ?? ""}</p>
            </div>
            <pre className="mt-3 max-h-[24rem] overflow-auto text-xs">
              {JSON.stringify(
                {
                  scores: result.explainability?.scores,
                  evidence: result.explainability?.evidence,
                  suspicious_parts: result.explainability?.suspicious_parts,
                  suspicious_timestamps: result.explainability?.suspicious_timestamps,
                },
                null,
                2,
              )}
            </pre>
          </article>

          <article className="rounded-lg border border-zinc-300 p-4 dark:border-zinc-700">
            <h2 className="mb-2 text-base font-semibold">Debug Trace</h2>
            <pre className="max-h-[28rem] overflow-auto text-xs">
              {JSON.stringify(
                {
                  traces: result.explainability?.traces,
                  debug: result.explainability?.debug,
                  raw_report: result.raw_report,
                },
                null,
                2,
              )}
            </pre>
          </article>
        </section>
      ) : null}
    </main>
  );
}
