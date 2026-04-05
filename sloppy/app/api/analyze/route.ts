import { NextRequest, NextResponse } from "next/server";

type InputPayload = {
  text?: string;
  image_base64?: string;
  content_type?: string;
  metadata?: Record<string, unknown>;
  element_id?: string;
};

type AnalyzeMode = "orchestrator" | "direct";

const ORCHESTRATOR_URL = process.env.ORCHESTRATOR_URL ?? "http://localhost:8080";
const ANONYMIZER_URL = process.env.ANONYMIZER_URL ?? "http://localhost:8081";
const ML_SERVICE_URL = process.env.ML_SERVICE_URL ?? "http://localhost:8082";
const TRUTH_SERVICE_URL = process.env.TRUTH_SERVICE_URL ?? "http://localhost:8083";
const CONTEXT_SERVICE_URL =
  process.env.CONTEXT_SERVICE_URL ?? "http://localhost:8084";

const REQUEST_TIMEOUT_MS = 15000;

function summarizePayload(payload: InputPayload) {
  const text = payload.text ?? "";
  const image = payload.image_base64 ?? "";
  const metadata = payload.metadata ?? {};
  return {
    content_type: payload.content_type ?? "text",
    text_len: text.length,
    has_image: image.length > 0,
    image_b64_len: image.length,
    metadata_keys: Object.keys(metadata),
  };
}

async function postJSON<TBody extends object, TResp = unknown>(
  url: string,
  body: TBody,
): Promise<TResp> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), REQUEST_TIMEOUT_MS);
  const started = Date.now();

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: ctrl.signal,
      cache: "no-store",
    });

    const payload = (await response.json().catch(() => ({}))) as TResp;
    if (!response.ok) {
      console.error("[web-api] downstream non-ok", {
        url,
        status: response.status,
        elapsed_ms: Date.now() - started,
      });
      const detail =
        typeof payload === "object" && payload !== null && "detail" in payload
          ? String((payload as { detail?: unknown }).detail)
          : `HTTP ${response.status}`;
      throw new Error(detail);
    }

    console.info("[web-api] downstream ok", {
      url,
      status: response.status,
      elapsed_ms: Date.now() - started,
    });

    return payload;
  } catch (error) {
    console.error("[web-api] downstream fetch failed", {
      url,
      elapsed_ms: Date.now() - started,
      error: error instanceof Error ? error.message : String(error),
    });
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function looksLikeNews(text: string): boolean {
  const signals = [
    "breaking",
    "exclusive",
    "report",
    "president",
    "minister",
    "attack",
    "killed",
    "war",
    "crisis",
    "government",
    "official",
    "election",
    "court",
    "police",
    "military",
    "announced",
    "confirmed",
    "according to",
    "sources say",
    "just in",
    "developing",
  ];

  const haystack = text.toLowerCase();
  const count = signals.reduce(
    (acc, signal) => acc + (haystack.includes(signal) ? 1 : 0),
    0,
  );
  return count >= 2;
}

export async function POST(req: NextRequest) {
  const started = Date.now();
  try {
    const {
      mode = "orchestrator",
      payload,
      runTruth = true,
    }: {
      mode?: AnalyzeMode;
      payload?: InputPayload;
      runTruth?: boolean;
    } = await req.json();

    if (!payload || typeof payload !== "object") {
      return NextResponse.json(
        { error: "Missing payload object" },
        { status: 400 },
      );
    }

    console.info("[web-api] analyze start", {
      mode,
      runTruth,
      payload: summarizePayload(payload),
    });

    if (mode === "orchestrator") {
      const result = await postJSON(`${ORCHESTRATOR_URL}/analyze`, payload);
      console.info("[web-api] analyze done", {
        mode,
        elapsed_ms: Date.now() - started,
      });
      return NextResponse.json({ mode, result });
    }

    const rawText = payload.text ?? "";
    const anonymized = await postJSON<InputPayload, Record<string, unknown>>(
      `${ANONYMIZER_URL}/anonymize`,
      payload,
    );

    const baseRequest = {
      session_id: String(anonymized.session_id ?? ""),
      clean_text: String(anonymized.clean_text ?? ""),
      clean_image_base64: String(anonymized.clean_image_base64 ?? ""),
      content_type: String(anonymized.content_type ?? payload.content_type ?? "text"),
      metadata:
        (anonymized.metadata as Record<string, unknown> | undefined) ??
        payload.metadata ??
        {},
    };

    const [classifier, contextMl, contextConfidence, source] = await Promise.allSettled([
      postJSON(`${ML_SERVICE_URL}/classify`, baseRequest),
      postJSON(`${ML_SERVICE_URL}/context`, baseRequest),
      postJSON(`${CONTEXT_SERVICE_URL}/context`, baseRequest),
      postJSON(`${TRUTH_SERVICE_URL}/source`, baseRequest),
    ]);

    const shouldRunTruth = runTruth && looksLikeNews(baseRequest.clean_text);
    const truth = shouldRunTruth
      ? await Promise.resolve(
          postJSON(`${TRUTH_SERVICE_URL}/truth`, {
            ...baseRequest,
            clean_text: rawText || baseRequest.clean_text,
          }).then(
            (value) => ({ status: "fulfilled", value }) as const,
            (reason) => ({ status: "rejected", reason }) as const,
          ),
        )
      : ({
          status: "fulfilled",
          value: {
            skipped: true,
            reason: runTruth
              ? "Heuristic: content does not look like a news claim"
              : "User skipped truth retrieval",
          },
        } as const);

    const normalizeSettled = (
      settled: PromiseSettledResult<unknown> | { status: "fulfilled"; value: unknown } | { status: "rejected"; reason: unknown },
    ) => {
      if (settled.status === "fulfilled") {
        return { ok: true, data: settled.value };
      }
      return {
        ok: false,
        error:
          settled.reason instanceof Error
            ? settled.reason.message
            : String(settled.reason),
      };
    };

    const mergedContext = (() => {
      if (contextMl.status !== "fulfilled" && contextConfidence.status !== "fulfilled") {
        return {
          ok: false,
          error: "Both context providers failed",
        };
      }

      const ml =
        contextMl.status === "fulfilled" &&
        contextMl.value &&
        typeof contextMl.value === "object"
          ? (contextMl.value as Record<string, unknown>)
          : null;

      const cc =
        contextConfidence.status === "fulfilled" &&
        contextConfidence.value &&
        typeof contextConfidence.value === "object"
          ? (contextConfidence.value as Record<string, unknown>)
          : null;

      if (ml && cc) {
        const mlConfidence = Number(ml.confidence ?? 0);
        const ccConfidence = Number(cc.confidence ?? 0);
        return {
          ok: true,
          data: {
            is_misleading: Boolean(ml.is_misleading) || Boolean(cc.is_misleading),
            confidence: Number((mlConfidence * 0.55 + ccConfidence * 0.45).toFixed(4)),
            explanation: `ML: ${String(ml.explanation ?? "")}` +
              ` | Heuristic: ${String(cc.explanation ?? "")}`,
            provider: "ml+context-confidence",
            providers: {
              ml,
              context_confidence: cc,
            },
          },
        };
      }

      if (ml) {
        return {
          ok: true,
          data: {
            ...ml,
            provider: "ml-engine",
          },
        };
      }

      return {
        ok: true,
        data: {
          ...(cc ?? {}),
          provider: "context-confidence",
        },
      };
    })();

    return NextResponse.json({
      mode,
      anonymized,
      services: {
        classifier: normalizeSettled(classifier),
        context: mergedContext,
        context_ml: normalizeSettled(contextMl),
        context_confidence: normalizeSettled(contextConfidence),
        source: normalizeSettled(source),
        truth: normalizeSettled(truth),
      },
    });
  } catch (error) {
    console.error("[web-api] analyze failed", {
      elapsed_ms: Date.now() - started,
      error: error instanceof Error ? error.message : String(error),
    });
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Unexpected error",
      },
      { status: 500 },
    );
  }
}
