import { NextRequest, NextResponse } from "next/server";

const ML_SERVICE_URL = process.env.ML_SERVICE_URL ?? "http://localhost:8082";
const REQUEST_TIMEOUT_MS = 180000;

type DownstreamTrace = {
  service: string;
  method: "GET" | "POST";
  url: string;
  ok: boolean;
  status?: number;
  elapsed_ms: number;
  request_body?: unknown;
  response_body?: unknown;
  error?: string;
};

type DownstreamResult = {
  ok: boolean;
  data?: unknown;
  error?: string;
  trace: DownstreamTrace;
};

async function callDownstream(
  service: string,
  method: "GET" | "POST",
  url: string,
  body?: unknown,
): Promise<DownstreamResult> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), REQUEST_TIMEOUT_MS);
  const started = Date.now();

  try {
    const response = await fetch(url, {
      method,
      headers: method === "POST" ? { "Content-Type": "application/json" } : undefined,
      body: method === "POST" ? JSON.stringify(body ?? {}) : undefined,
      signal: ctrl.signal,
      cache: "no-store",
    });

    const payload = (await response.json().catch(() => ({}))) as unknown;
    const elapsed = Date.now() - started;

    if (!response.ok) {
      const detail =
        typeof payload === "object" && payload !== null && "detail" in payload
          ? String((payload as { detail?: unknown }).detail)
          : `HTTP ${response.status}`;

      return {
        ok: false,
        error: detail,
        trace: {
          service,
          method,
          url,
          ok: false,
          status: response.status,
          elapsed_ms: elapsed,
          request_body: body,
          response_body: payload,
          error: detail,
        },
      };
    }

    return {
      ok: true,
      data: payload,
      trace: {
        service,
        method,
        url,
        ok: true,
        status: response.status,
        elapsed_ms: elapsed,
        request_body: body,
        response_body: payload,
      },
    };
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    return {
      ok: false,
      error: detail,
      trace: {
        service,
        method,
        url,
        ok: false,
        elapsed_ms: Date.now() - started,
        request_body: body,
        error: detail,
      },
    };
  } finally {
    clearTimeout(timer);
  }
}

export async function POST(req: NextRequest) {
  const payload = (await req.json()) as Record<string, unknown>;

  const context = await callDownstream(
    "classifier_context",
    "POST",
    `${ML_SERVICE_URL}/v1/context/analyze`,
    payload,
  );

  if (!context.ok || typeof context.data !== "object" || !context.data) {
    return NextResponse.json(
      {
        error: context.error ?? "classifier_context_failed",
        services: { classifier_context: context },
        explainability: {
          traces: [context.trace],
        },
      },
      { status: 502 },
    );
  }

  const contextData = context.data as Record<string, unknown>;

  return NextResponse.json({
    services: {
      classifier_context: context,
    },
    explainability: {
      explanation: contextData.explanation ?? "",
      context_scores: contextData.context_scores ?? null,
      references: contextData.references ?? [],
      suspicious_parts: contextData.suspicious_parts ?? [],
      signals: (contextData.debug as Record<string, unknown> | undefined)?.context
        ? ((contextData.debug as Record<string, unknown>).context as Record<string, unknown>).rules ?? []
        : [],
      debug: contextData.debug ?? {},
      traces: [context.trace],
    },
    raw: contextData,
  });
}
