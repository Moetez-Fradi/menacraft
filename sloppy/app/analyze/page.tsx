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

const PAGE_COPY = {
  headerTitle: "Analyze a post or claim",
  headerSubtitle:
    "Paste text or upload media, then we run authenticity analysis and show a plain-language summary.",
  requestTitle: "1) What should we analyze?",
  requestSubtitle:
    "Choose one input mode so the system knows whether to read text or extract details from media.",
  resultTitle: "2) Result summary",
  resultSubtitle:
    "This section explains the verdict in simple terms and shows the main supporting signals.",
  advancedTitle: "Advanced technical output",
  advancedSubtitle:
    "Raw traces for troubleshooting. Most users can ignore this section.",
};

const CONTENT_TYPE_OPTIONS = [
  { value: "text", label: "Text" },
  { value: "image", label: "Image" },
  { value: "video", label: "Video" },
] as const;

export default function AnalyzePage() {
  const [sessionId] = useState(`manual-${Date.now()}`);
  const [text, setText] = useState("");
  const [contentType, setContentType] = useState<(typeof CONTENT_TYPE_OPTIONS)[number]["value"]>("text");
  const [platform, setPlatform] = useState("web");
  const [linksInput, setLinksInput] = useState("");
  const [extraMetadataJson, setExtraMetadataJson] = useState("{}");
  const [imageBase64, setImageBase64] = useState("");
  const [selectedFileName, setSelectedFileName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<AnalyzeResponse | null>(null);

  const requiresMediaUpload = contentType === "image" || contentType === "video";

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
      if (!requiresMediaUpload && !text.trim()) {
        throw new Error("Please add text to analyze.");
      }
      if (requiresMediaUpload && !imageBase64) {
        throw new Error("Please upload a media file before running analysis.");
      }

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
          text: requiresMediaUpload ? "" : text,
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
    <main className="app-page">
      <header className="app-header panel p-5 md:p-6">
        <span className="endpoint-kicker">Classifier</span>
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
              Input Mode
              <select
                className="input-control"
                value={contentType}
                onChange={(event) => {
                  const nextType = event.target.value as (typeof CONTENT_TYPE_OPTIONS)[number]["value"];
                  setContentType(nextType);
                  setImageBase64("");
                  setSelectedFileName("");
                }}
              >
                {CONTENT_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
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

          <p className="muted-note">
            Session ID is auto-generated for tracking: <span className="font-mono">{sessionId}</span>
          </p>

          {!requiresMediaUpload ? (
            <label className="form-label">
              Text to analyze
              <textarea
                className="input-control min-h-32"
                value={text}
                onChange={(event) => setText(event.target.value)}
                placeholder="Paste the claim or post text"
                required
              />
            </label>
          ) : (
            <label className="form-label">
              Upload {contentType}
              <input
                className="input-control"
                type="file"
                accept={contentType === "video" ? "video/*" : "image/*"}
                onChange={handleFileInput}
                required
              />
              <span className="form-hint">
                {selectedFileName
                  ? `Loaded: ${selectedFileName}`
                  : contentType === "video"
                    ? "We automatically extract the first frame from the video."
                    : "Upload one image file to analyze."}
              </span>
            </label>
          )}

          <label className="form-label">
            Optional links (comma or newline separated)
            <textarea
              className="input-control min-h-20"
              value={linksInput}
              onChange={(event) => setLinksInput(event.target.value)}
              placeholder="https://example.com/news-1"
            />
          </label>

          <label className="form-label">
            Optional metadata (JSON)
            <textarea
              className="input-control min-h-24 font-mono text-xs"
              value={extraMetadataJson}
              onChange={(event) => setExtraMetadataJson(event.target.value)}
            />
          </label>

          <button
            className="primary-btn"
            disabled={loading}
            type="submit"
          >
            {loading ? "Running..." : "Analyze now"}
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
                Case: {result.case_id ?? "n/a"}
              </span>
              <span className="stat-chip">
                Verdict: {result.explainability?.verdict ?? "n/a"}
              </span>
            </div>
            <div className="space-y-2 text-sm">
              <p><strong>Explanation:</strong> {result.explainability?.explanation ?? ""}</p>
            </div>
            <pre className="code-block">
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

          <article className="panel p-5">
            <h2 className="section-title">{PAGE_COPY.advancedTitle}</h2>
            <p className="section-description mb-3">{PAGE_COPY.advancedSubtitle}</p>
            <details>
              <summary className="cursor-pointer text-sm font-medium text-violet-700 dark:text-violet-300">
                Show advanced JSON
              </summary>
              <pre className="code-block max-h-[32rem]">
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
            </details>
          </article>
        </section>
      ) : null}
    </main>
  );
}
