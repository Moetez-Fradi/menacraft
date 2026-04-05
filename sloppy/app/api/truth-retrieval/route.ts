import { NextRequest, NextResponse } from "next/server";

const TRUTH_SERVICE_URL = process.env.TRUTH_SERVICE_URL ?? "http://localhost:8083";
const REQUEST_TIMEOUT_MS = 120000;

type DownstreamTrace = {
  service: string;
  method: "POST";
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

async function callDownstream(url: string, body: unknown): Promise<DownstreamResult> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), REQUEST_TIMEOUT_MS);
  const started = Date.now();

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
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
          service: "truth_retrieval",
          method: "POST",
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
        service: "truth_retrieval",
        method: "POST",
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
        service: "truth_retrieval",
        method: "POST",
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
  const downstream = await callDownstream(`${TRUTH_SERVICE_URL}/truth`, payload);

  if (!downstream.ok) {
    return NextResponse.json(
      {
        error: downstream.error ?? "truth_retrieval_failed",
        service: downstream,
        explainability: {
          traces: [downstream.trace],
        },
      },
      { status: 502 },
    );
  }

  return NextResponse.json({
    ...(downstream.data as Record<string, unknown>),
    service: downstream,
    explainability: {
      traces: [downstream.trace],
    },
  });
}
