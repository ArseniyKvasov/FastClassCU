import type { JSONContent } from "@tiptap/core";
import { Hocuspocus, type onAuthenticatePayload } from "@hocuspocus/server";
import { Redis } from "@hocuspocus/extension-redis";
import { Redis as IORedis } from "ioredis";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { URL } from "node:url";
import WebSocket, { WebSocketServer } from "ws";
import * as Y from "yjs";
import { logError, logInfo, withRequestContext } from "@fastclass/node-shared";

import { getAnswerSnapshot, healthcheckAnswers, pushAnswerSnapshot } from "./answers-client.js";
import { AuthError, issueCollabToken, verifyAuthToken, verifyCollabToken } from "./auth.js";
import { settings } from "./config.js";
import { isTeacherOfContext } from "./context-client.js";
import { buildRoomId } from "./room.js";
import { emptyDocumentJson, jsonToYDoc } from "./schema.js";
import { CollabStorage } from "./storage.js";
import type { AuthUser, SessionContext, SessionRequest } from "./types.js";

const storage = new CollabStorage();
const redis = new IORedis(settings.redisUrl);

function json(response: ServerResponse, statusCode: number, payload: unknown): void {
  response.writeHead(statusCode, { "Content-Type": "application/json" });
  response.end(JSON.stringify(payload));
}

function text(response: ServerResponse, statusCode: number, body: string): void {
  response.writeHead(statusCode, { "Content-Type": "text/plain; charset=utf-8" });
  response.end(body);
}

function getBearerToken(request: IncomingMessage): string {
  const header = request.headers.authorization;
  if (!header?.startsWith("Bearer ")) {
    throw new AuthError("Missing bearer token");
  }
  return header.slice("Bearer ".length);
}

async function readJsonBody(request: IncomingMessage): Promise<any> {
  const chunks: Buffer[] = [];
  for await (const chunk of request) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  const raw = Buffer.concat(chunks).toString("utf-8");
  return raw ? JSON.parse(raw) : {};
}

function isSessionRequest(body: any): body is SessionRequest {
  return (
    body &&
    typeof body.task_id === "string" &&
    (body.context_type === "classroom" || body.context_type === "assignment") &&
    typeof body.context_id === "string" &&
    typeof body.owner_user_id === "string"
  );
}

async function authorizeSession(
  request: SessionRequest,
  user: AuthUser,
): Promise<SessionContext> {
  const roomId = buildRoomId(request);
  if (user.userId === request.owner_user_id) {
    return {
      ...request,
      roomId,
      actorUserId: user.userId,
      actorRole: "owner",
    };
  }

  const isTeacher = await isTeacherOfContext({
    contextType: request.context_type,
    contextId: request.context_id,
    actorUserId: user.userId,
    bearerToken: user.rawToken,
  });
  if (!isTeacher) {
    throw new AuthError("Forbidden");
  }

  return {
    ...request,
    roomId,
    actorUserId: user.userId,
    actorRole: "teacher",
  };
}

function buildWsUrl(request: IncomingMessage): string {
  if (settings.publicWsBaseUrl) {
    return `${settings.publicWsBaseUrl}${settings.wsPath}`;
  }
  const protocol = request.headers["x-forwarded-proto"] ?? "http";
  const host = request.headers["x-forwarded-host"] ?? request.headers.host ?? "localhost";
  const wsProtocol = String(protocol) === "https" ? "wss" : "ws";
  return `${wsProtocol}://${host}${settings.wsPath}`;
}

async function handleSessionRequest(
  request: IncomingMessage,
  response: ServerResponse,
): Promise<void> {
  try {
    const authUser = verifyAuthToken(getBearerToken(request));
    const body = await readJsonBody(request);
    if (!isSessionRequest(body)) {
      json(response, 400, { code: "invalid_request" });
      return;
    }
    const session = await authorizeSession(body, authUser);
    const collabToken = issueCollabToken(session);
    json(response, 200, {
      room_id: session.roomId,
      document_name: session.roomId,
      ws_url: buildWsUrl(request),
      token: collabToken,
      protocol: "hocuspocus",
      field_name: settings.roomFieldName,
    });
  } catch (error) {
    if (error instanceof AuthError) {
      json(response, 401, { code: "unauthorized" });
      return;
    }
    logError("session_error", error);
    json(response, 500, { code: "internal_error" });
  }
}

async function seedDocument(context: SessionContext): Promise<Y.Doc> {
  const snapshot = await getAnswerSnapshot({
    taskId: context.task_id,
    userId: context.owner_user_id,
    contextType: context.context_type,
    contextId: context.context_id,
  });

  let source: JSONContent | null = null;
  if (snapshot?.document_json) {
    source = snapshot.document_json;
  } else if (snapshot?.text) {
    try {
      source = JSON.parse(snapshot.text) as JSONContent;
    } catch {
      source = {
        type: "doc",
        content: [
          {
            type: "paragraph",
            content: snapshot.text
              ? [
                  {
                    type: "text",
                    text: snapshot.text,
                  },
                ]
              : [],
          },
        ],
      };
    }
  }

  return jsonToYDoc(source ?? emptyDocumentJson());
}

const hocuspocus = new Hocuspocus<SessionContext>({
  debounce: settings.hocuspocusDebounceMs,
  maxDebounce: settings.hocuspocusMaxDebounceMs,
  extensions: [
    new Redis({
      redis,
    }),
  ],
  async onAuthenticate(data: onAuthenticatePayload<SessionContext>) {
    const context = verifyCollabToken(data.token);
    if (data.documentName !== context.roomId) {
      throw new Error("document/token mismatch");
    }
    Object.assign(data.context, context);
  },
  async onLoadDocument({ context, documentName }) {
    const row = await storage.getDocument(documentName);
    if (row?.yjs_state) {
      const doc = new Y.Doc();
      Y.applyUpdate(doc, new Uint8Array(row.yjs_state));
      return doc;
    }
    return seedDocument(context);
  },
  async onStoreDocument({ document, lastContext, documentName }) {
    if (!lastContext) {
      return;
    }
    if (documentName !== lastContext.roomId) {
      throw new Error("store context mismatch");
    }

    const persisted = await storage.saveDocument(lastContext, document);
    await pushAnswerSnapshot({
      taskId: lastContext.task_id,
      userId: lastContext.owner_user_id,
      contextType: lastContext.context_type,
      contextId: lastContext.context_id,
      documentJson: persisted.documentJson,
      plainText: persisted.plainText,
      revision: persisted.revision,
    });
  },
});

async function handleHttp(request: IncomingMessage, response: ServerResponse): Promise<void> {
  const url = new URL(request.url ?? "/", `http://${request.headers.host ?? "localhost"}`);

  if (request.method === "GET" && url.pathname === "/health") {
    json(response, 200, { status: "ok" });
    return;
  }

  if (request.method === "GET" && url.pathname === "/ready") {
    try {
      await storage.healthcheck();
      await redis.ping();
      await healthcheckAnswers();
      json(response, 200, { status: "ready" });
    } catch (error) {
      logError("readiness_error", error);
      json(response, 503, { status: "degraded" });
    }
    return;
  }

  if (request.method === "POST" && url.pathname === "/collab/sessions") {
    await handleSessionRequest(request, response);
    return;
  }

  text(response, 404, "Not found");
}

const httpServer = createServer((request, response) => {
  withRequestContext(request.headers, async () => {
    await handleHttp(request, response);
  }).catch((error) => {
    logError("http_error", error, {
      method: request.method,
      path: request.url,
    });
    json(response, 500, { code: "internal_error" });
  });
});

const websocketServer = new WebSocketServer({
  noServer: true,
});

httpServer.on("upgrade", (request, socket, head) => {
  const url = new URL(request.url ?? "/", `http://${request.headers.host ?? "localhost"}`);
  if (url.pathname !== settings.wsPath) {
    socket.write("HTTP/1.1 404 Not Found\r\n\r\n");
    socket.destroy();
    return;
  }

  websocketServer.handleUpgrade(request, socket, head, (websocket) => {
    const protocol = request.headers["x-forwarded-proto"] ?? "http";
    const host = request.headers["x-forwarded-host"] ?? request.headers.host ?? "localhost";
    const req = new Request(`${protocol}://${host}${request.url ?? settings.wsPath}`, {
      method: request.method ?? "GET",
      headers: request.headers as Record<string, string>,
    });
    // `handleConnection` only builds the protocol handler - per @hocuspocus/
    // server's own "Non-Node.js runtimes" integration contract, the caller
    // (us) is responsible for pumping the raw socket's message/close events
    // into it. Skipping this wiring lets the WS handshake succeed while
    // every sync/auth message from the client goes nowhere - a silent hang,
    // not an error, which is exactly what made it hard to notice.
    const clientConnection = hocuspocus.handleConnection(
      websocket as unknown as WebSocket,
      req,
      {} as SessionContext,
    );
    websocket.on("message", (data) => {
      let bytes: Buffer;
      if (Array.isArray(data)) {
        bytes = Buffer.concat(data);
      } else if (data instanceof ArrayBuffer) {
        bytes = Buffer.from(data);
      } else {
        bytes = data;
      }
      clientConnection.handleMessage(bytes);
    });
    websocket.on("close", (code, reason) => {
      clientConnection.handleClose({ code, reason: reason.toString() });
    });
    websocket.on("error", (error) => {
      logError("websocket_error", error);
    });
  });
});

async function shutdown(): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    httpServer.close((error) => {
      if (error) {
        reject(error);
        return;
      }
      resolve();
    });
  });
  hocuspocus.closeConnections();
  await redis.quit();
  await storage.close();
}

async function start(): Promise<void> {
  await new Promise<void>((resolve) => {
    httpServer.listen(settings.port, resolve);
  });
  logInfo("collaboration_service_started", { port: settings.port });
}

process.on("SIGINT", () => {
  shutdown()
    .then(() => process.exit(0))
    .catch(() => process.exit(1));
});
process.on("SIGTERM", () => {
  shutdown()
    .then(() => process.exit(0))
    .catch(() => process.exit(1));
});

start().catch((error) => {
  logError("startup_error", error);
  process.exit(1);
});
