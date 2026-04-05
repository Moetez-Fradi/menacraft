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

const PAGE_COPY = {
  headerTitle: "Check context around a claim",
  headerSubtitle:
    "Use an existing case ID and a new claim to test whether context supports or contradicts it.",
  requestTitle: "1) Provide claim context",
  requestSubtitle:
    "Enter the case ID and claim text. Add links/files only when they can improve context quality.",
  resultTitle: "2) Context consistency result",
  resultSubtitle:
    "Review signals, references, and explanation generated from the context analysis.",
  advancedTitle: "Advanced technical output",
  advancedSubtitle:
    "Raw traces for troubleshooting. Most users can ignore this section.",
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
    <main className="app-page">
      <header className="app-header panel p-5 md:p-6">
        <span className="endpoint-kicker">Context</span>
        <h1 className="app-title">{PAGE_COPY.headerTitle}</h1>
        <p className="app-subtitle">{PAGE_COPY.headerSubtitle}</p>
      </header>

      <section className="panel p-5 md:p-6">
        <div className="mb-4 space-y-1">
          <h2 className="section-title">{PAGE_COPY.requestTitle}</h2>
          <p className="section-description">{PAGE_COPY.requestSubtitle}</p>
        </div>

        <form className="space-y-5" onSubmit={onSubmit}>
          <label className="form-label">
            Case ID
            <input
              className="input-control"
              value={caseId}
              onChange={(event) => setCaseId(event.target.value)}
              placeholder="Use case_id returned by Analyze"
              required
            />
          </label>

          <label className="form-label">
            Claim text
            <textarea
              className="input-control min-h-28"
              value={claimText}
              onChange={(event) => setClaimText(event.target.value)}
              placeholder="Claim to validate against stored case artifacts"
              required
            />
          </label>

          <label className="form-label">
            Optional links (comma or newline separated)
            <textarea
              className="input-control min-h-20"
              value={linksInput}
              onChange={(event) => setLinksInput(event.target.value)}
              placeholder="https://example.com/context-reference"
            />
          </label>

          <label className="form-label">
            Optional files
            <input
              className="input-control"
              type="file"
              multiple
              onChange={handleFileInput}
            />
            <span className="form-hint">
              {selectedFileNames.length
                ? `Loaded: ${selectedFileNames.join(", ")}`
                : "Files are sent as base64 in platform_metadata.files."}
            </span>
          </label>

          <label className="form-label">
            Optional platform metadata (JSON)
            <textarea
              className="input-control min-h-24 font-mono text-xs"
              value={platformMetadataJson}
              onChange={(event) => setPlatformMetadataJson(event.target.value)}
            />
          </label>

          <button
            className="primary-btn"
            disabled={loading}
            type="submit"
          >
            {loading ? "Running..." : "Check context"}
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
                Signals: {Array.isArray(result.explainability?.signals) ? result.explainability?.signals.length : 0}
              </span>
              <span className="stat-chip">
                References: {Array.isArray(result.explainability?.references) ? result.explainability?.references.length : 0}
              </span>
            </div>
            <div className="space-y-2 text-sm">
              <p><strong>Explanation:</strong> {result.explainability?.explanation ?? ""}</p>
            </div>
            <pre className="code-block">
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
                    raw: result.raw,
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
