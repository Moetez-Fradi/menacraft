"use client";

import { ChangeEvent, FormEvent, useState } from "react";

type ContextResponse = {
  explainability?: {
    explanation?: string;
    context_scores?: unknown;
    references?: unknown[];
    suspicious_parts?: unknown[];
    signals?: unknown[];
    debug?: unknown;
    traces?: unknown[];
  };
  raw?: unknown;
  error?: string;
};

type UploadedContextFile = {
  name: string;
  mime_type: string;
  data_base64: string;
};

export default function ContextPage() {
  const [caseId, setCaseId] = useState("");
  const [claimText, setClaimText] = useState("");
  const [linksInput, setLinksInput] = useState("");
  const [platformMetadataJson, setPlatformMetadataJson] = useState('{"platform":"web"}');
  const [uploadedFiles, setUploadedFiles] = useState<UploadedContextFile[]>([]);
  const [selectedFileNames, setSelectedFileNames] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ContextResponse | null>(null);

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

  async function handleFileInput(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    setError("");

    if (!files.length) {
      setUploadedFiles([]);
      setSelectedFileNames([]);
      return;
    }

    try {
      const converted = await Promise.all(
        files.map(async (file) => ({
          name: file.name,
          mime_type: file.type || "application/octet-stream",
          data_base64: await toBase64(file),
        })),
      );

      setUploadedFiles(converted);
      setSelectedFileNames(converted.map((file) => file.name));
    } catch (fileError) {
      setError(
        fileError instanceof Error
          ? fileError.message
          : "Failed to process selected files",
      );
      setUploadedFiles([]);
      setSelectedFileNames([]);
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const platformMetadata = JSON.parse(platformMetadataJson) as Record<string, unknown>;
      const links = parseLinks(linksInput);

      const platform_metadata: Record<string, unknown> = {
        ...platformMetadata,
        ...(links.length ? { links } : {}),
        ...(uploadedFiles.length ? { files: uploadedFiles } : {}),
      };

      const response = await fetch("/api/classifier/context", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: caseId,
          claim_text: claimText,
          platform_metadata,
        }),
      });

      const body = (await response.json()) as ContextResponse;
      if (!response.ok) {
        throw new Error(body.error || `Request failed (${response.status})`);
      }
      setResult(body);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Unexpected error while calling /v1/context/analyze",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-4 py-8 md:px-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Classifier Endpoint: /v1/context/analyze</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-300">
          Evaluate contextual consistency and inspect reasoning signals and evidence references.
        </p>
      </header>

      <section className="rounded-lg border border-zinc-300 p-4 dark:border-zinc-700">
        <form className="space-y-4" onSubmit={onSubmit}>
          <label className="flex flex-col gap-1 text-sm">
            Case ID
            <input
              className="rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
              value={caseId}
              onChange={(event) => setCaseId(event.target.value)}
              placeholder="Use case_id returned by /v1/analyze"
              required
            />
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Claim Text
            <textarea
              className="min-h-28 rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
              value={claimText}
              onChange={(event) => setClaimText(event.target.value)}
              placeholder="Claim to validate against stored case artifacts"
              required
            />
          </label>

            <label className="flex flex-col gap-1 text-sm">
              Links (comma or newline separated)
              <textarea
                className="min-h-20 rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
                value={linksInput}
                onChange={(event) => setLinksInput(event.target.value)}
                placeholder="https://example.com/context-reference"
              />
            </label>

            <label className="flex flex-col gap-1 text-sm">
              Files (optional)
              <input
                className="rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
                type="file"
                multiple
                onChange={handleFileInput}
              />
              <span className="text-xs text-zinc-500 dark:text-zinc-400">
                {selectedFileNames.length
                  ? `Loaded: ${selectedFileNames.join(", ")}`
                  : "Selected files are sent as base64 in platform_metadata.files."}
              </span>
            </label>

          <label className="flex flex-col gap-1 text-sm">
            Platform Metadata (JSON)
            <textarea
              className="min-h-24 rounded border border-zinc-300 bg-transparent px-3 py-2 font-mono text-xs dark:border-zinc-700"
              value={platformMetadataJson}
              onChange={(event) => setPlatformMetadataJson(event.target.value)}
            />
          </label>

          <button
            className="rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
            disabled={loading}
            type="submit"
          >
            {loading ? "Running..." : "Run /v1/context/analyze"}
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
              <p><strong>Explanation:</strong> {result.explainability?.explanation ?? ""}</p>
            </div>
            <pre className="mt-3 max-h-[24rem] overflow-auto text-xs">
              {JSON.stringify(
                {
                  context_scores: result.explainability?.context_scores,
                  signals: result.explainability?.signals,
                  suspicious_parts: result.explainability?.suspicious_parts,
                  references: result.explainability?.references,
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
                  raw: result.raw,
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
