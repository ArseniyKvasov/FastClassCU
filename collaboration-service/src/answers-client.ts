import type { JSONContent } from "@tiptap/core";
import { propagateHeaders } from "@fastclass/node-shared";

import { settings } from "./config.js";
import { getServiceAuthHeaders } from "./service-auth.js";
import type { AnswersSnapshot, ContextType } from "./types.js";

async function parseJsonResponse(response: Response): Promise<any> {
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

export async function getAnswerSnapshot(params: {
  taskId: string;
  userId: string;
  contextType: ContextType;
  contextId: string;
}): Promise<AnswersSnapshot | null> {
  const url = new URL("/internal/collab-snapshot", settings.answersServiceBaseUrl);
  url.searchParams.set("task_id", params.taskId);
  url.searchParams.set("user_id", params.userId);
  url.searchParams.set("context_type", params.contextType);
  url.searchParams.set("context_id", params.contextId);

  const response = await fetch(url, {
    method: "GET",
    headers: propagateHeaders((await getServiceAuthHeaders()) as Record<string, string>),
  });

  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Answers snapshot fetch failed with ${response.status}`);
  }
  return (await parseJsonResponse(response)) as AnswersSnapshot;
}

export async function pushAnswerSnapshot(body: {
  taskId: string;
  userId: string;
  contextType: ContextType;
  contextId: string;
  documentJson: JSONContent;
  plainText: string;
  revision: number;
}): Promise<void> {
  const response = await fetch(
    new URL("/internal/collab-snapshot", settings.answersServiceBaseUrl),
    {
      method: "POST",
      headers: propagateHeaders((await getServiceAuthHeaders()) as Record<string, string>),
      body: JSON.stringify({
        task_id: body.taskId,
        user_id: body.userId,
        context_type: body.contextType,
        context_id: body.contextId,
        document_json: body.documentJson,
        plain_text: body.plainText,
        revision: body.revision,
      }),
    },
  );

  if (!response.ok) {
    throw new Error(`Answers snapshot push failed with ${response.status}`);
  }
}

export async function healthcheckAnswers(): Promise<void> {
  const response = await fetch(new URL("/health", settings.answersServiceBaseUrl), {
    method: "GET",
    headers: propagateHeaders(),
  });
  if (!response.ok) {
    throw new Error(`Answers healthcheck failed with ${response.status}`);
  }
}
