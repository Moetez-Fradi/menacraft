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

  const accepted = await callDownstream(
    "classifier_accept",
    "POST",
    `${ML_SERVICE_URL}/v1/analyze`,
    payload,
  );

  if (!accepted.ok || typeof accepted.data !== "object" || !accepted.data) {
    return NextResponse.json(
      {
        error: accepted.error ?? "classifier_accept_failed",
        services: { classifier_accepted: accepted },
        explainability: {
          traces: [accepted.trace],
        },
      },
      { status: 502 },
    );
  }

  const caseId = String((accepted.data as { case_id?: unknown }).case_id ?? "");
  if (!caseId) {
    return NextResponse.json(
      {
        error: "classifier_accept_missing_case_id",
        services: { classifier_accepted: accepted },
        explainability: {
          traces: [accepted.trace],
        },
      },
      { status: 502 },
    );
  }

  const report = await callDownstream(
    "classifier_report",
    "GET",
    `${ML_SERVICE_URL}/v1/cases/${caseId}/report`,
  );

  const reportData =
    report.ok && report.data && typeof report.data === "object"
      ? (report.data as Record<string, unknown>)
      : null;

  return NextResponse.json({
    case_id: caseId,
    services: {
      classifier_accepted: accepted,
      classifier_report: report,
    },
    explainability: {
      explanation: reportData?.explanation ?? "",
      verdict: reportData?.verdict ?? null,
      scores: reportData?.scores ?? null,
      evidence: reportData?.evidence ?? [],
      suspicious_parts: reportData?.suspicious_parts ?? [],
      suspicious_timestamps: reportData?.suspicious_timestamps ?? [],
      debug: reportData?.debug ?? {},
      traces: [accepted.trace, report.trace],
    },
    raw_report: reportData,
  });
}
