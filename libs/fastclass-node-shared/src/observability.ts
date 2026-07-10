import { AsyncLocalStorage } from "node:async_hooks";
import { randomBytes, randomUUID } from "node:crypto";

type Context = {
  requestId: string;
  traceparent: string;
};

const storage = new AsyncLocalStorage<Context>();

function randomHex(bytes: number): string {
  return randomBytes(bytes).toString("hex");
}

function normalizeTraceparent(header?: string | null): string {
  const value = header?.trim();
  if (value && /^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$/i.test(value)) {
    return value.toLowerCase();
  }
  return `00-${randomHex(16)}-${randomHex(8)}-01`;
}

export function withRequestContext<T>(
  headers: Record<string, string | string[] | undefined>,
  fn: () => Promise<T>,
): Promise<T> {
  const requestId = String(headers["x-request-id"] ?? randomUUID());
  const traceparent = normalizeTraceparent(
    typeof headers.traceparent === "string" ? headers.traceparent : null,
  );
  return storage.run({ requestId, traceparent }, fn);
}

export function propagateHeaders(headers: Record<string, string> = {}): Record<string, string> {
  const context = storage.getStore();
  if (!context) {
    return headers;
  }
  return {
    ...headers,
    "X-Request-ID": headers["X-Request-ID"] ?? context.requestId,
    traceparent: headers.traceparent ?? context.traceparent,
  };
}

function log(level: "info" | "error", event: string, extra: Record<string, unknown> = {}): void {
  const context = storage.getStore();
  const payload = {
    timestamp: new Date().toISOString(),
    level,
    event,
    request_id: context?.requestId,
    traceparent: context?.traceparent,
    ...extra,
  };
  const line = JSON.stringify(payload);
  if (level === "error") {
    console.error(line);
  } else {
    console.log(line);
  }
}

export function logInfo(event: string, extra: Record<string, unknown> = {}): void {
  log("info", event, extra);
}

export function logError(event: string, error: unknown, extra: Record<string, unknown> = {}): void {
  log("error", event, {
    ...extra,
    error: error instanceof Error ? error.message : String(error),
  });
}
