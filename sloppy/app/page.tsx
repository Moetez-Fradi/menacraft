"use client";

import { ChangeEvent, FormEvent, useMemo, useState } from "react";

type Mode = "orchestrator" | "direct";
type ContentType = "text" | "post" | "image" | "video" | "audio" | "document";

type AnalysisResponse = {
  mode: Mode;
  result?: Record<string, unknown>;
  anonymized?: Record<string, unknown>;
  services?: Record<string, unknown>;
  error?: string;
};

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

export default function Home() {
  const [mode, setMode] = useState<Mode>("orchestrator");
  const [contentType, setContentType] = useState<ContentType>("text");
  const [text, setText] = useState("");
  const [link, setLink] = useState("");
  const [username, setUsername] = useState("");
  const [bio, setBio] = useState("");
  const [platform, setPlatform] = useState("web");
  const [imageBase64, setImageBase64] = useState("");
  const [selectedFileName, setSelectedFileName] = useState("");
  const [runTruth, setRunTruth] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [error, setError] = useState("");

  const metadata = useMemo(() => {
    const links = link.trim() ? [link.trim()] : [];
    return {
      platform,
      source_type: platform === "web" ? "web" : "social",
      language: "en",
      timestamp: new Date().toISOString(),
      ...(username.trim() ? { username: username.trim() } : {}),
      ...(bio.trim() ? { bio: bio.trim() } : {}),
      ...(links.length ? { links } : {}),
    };
  }, [bio, link, platform, username]);

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
      const payload = {
        element_id: `manual-${Date.now()}`,
        text: text.trim(),
        image_base64: imageBase64,
        content_type: contentType,
        metadata,
      };

      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode, payload, runTruth }),
      });

      const body = (await response.json()) as AnalysisResponse;
      if (!response.ok) {
        throw new Error(body.error || `Request failed (${response.status})`);
      }

      setResult(body);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Unexpected error while analyzing content",
      );
    } finally {
      setLoading(false);
    }
  }

  const orchestratorResult = result?.result;
  const directServices = result?.services;

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-4 py-8 md:px-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">MENACRAFT Manual Service Console</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-300">
          Test the same payload flow as the extension and inspect each axis result manually.
        </p>
      </header>

      <section className="rounded-lg border border-zinc-300 p-4 dark:border-zinc-700">
        <form className="space-y-4" onSubmit={onSubmit}>
          <div className="grid gap-4 md:grid-cols-3">
            <label className="flex flex-col gap-1 text-sm">
              Mode
              <select
                className="rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
                value={mode}
                onChange={(event) => setMode(event.target.value as Mode)}
              >
                <option value="orchestrator">Extension-compatible pipeline (/analyze)</option>
                <option value="direct">Direct services adapter (anonymize + axes)</option>
              </select>
            </label>

            <label className="flex flex-col gap-1 text-sm">
              Content Type
              <select
                className="rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
                value={contentType}
                onChange={(event) => {
                  setContentType(event.target.value as ContentType);
                  setImageBase64("");
                  setSelectedFileName("");
                }}
              >
                <option value="text">text</option>
                <option value="post">post</option>
                <option value="image">image</option>
                <option value="video">video</option>
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
            Text / Caption / Claim
            <textarea
              className="min-h-32 rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Paste content, post text, or claim here"
            />
          </label>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm">
              Link (optional)
              <input
                className="rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
                value={link}
                onChange={(event) => setLink(event.target.value)}
                placeholder="https://example.com/source"
              />
            </label>

            <label className="flex flex-col gap-1 text-sm">
              Account Username (optional)
              <input
                className="rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="account name or handle"
              />
            </label>
          </div>

          <label className="flex flex-col gap-1 text-sm">
            Account Bio / Description (optional)
            <input
              className="rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
              value={bio}
              onChange={(event) => setBio(event.target.value)}
              placeholder="Used by source credibility checks"
            />
          </label>

          <div className="grid gap-4 md:grid-cols-[2fr_1fr]">
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
                  : "For video, first frame is extracted and sent as image_base64."}
              </span>
            </label>

            <label className="mt-6 flex items-center gap-2 text-sm md:mt-0">
              <input
                checked={runTruth}
                onChange={(event) => setRunTruth(event.target.checked)}
                type="checkbox"
              />
              Enable truth retrieval
            </label>
          </div>

          <button
            className="rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
            disabled={loading}
            type="submit"
          >
            {loading ? "Analyzing..." : "Run Analysis"}
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
            <h2 className="mb-2 text-base font-semibold">Primary Result</h2>
            <pre className="max-h-[28rem] overflow-auto text-xs">
              {JSON.stringify(orchestratorResult ?? directServices, null, 2)}
            </pre>
          </article>

          <article className="rounded-lg border border-zinc-300 p-4 dark:border-zinc-700">
            <h2 className="mb-2 text-base font-semibold">Adapter Details</h2>
            <pre className="max-h-[28rem] overflow-auto text-xs">
              {JSON.stringify(
                {
                  mode: result.mode,
                  anonymized: result.anonymized,
                  full: result,
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
