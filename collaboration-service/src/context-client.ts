import { propagateHeaders } from "@fastclass/node-shared";

import { settings } from "./config.js";
import type { ContextType } from "./types.js";

export async function isTeacherOfContext(params: {
  contextType: ContextType;
  contextId: string;
  actorUserId: string;
  bearerToken: string;
}): Promise<boolean> {
  const baseUrl =
    params.contextType === "classroom"
      ? settings.classroomServiceBaseUrl
      : settings.assignmentsServiceBaseUrl;
  const path =
    params.contextType === "classroom"
      ? `/classrooms/${params.contextId}`
      : `/assignments/${params.contextId}`;

  const response = await fetch(new URL(path, baseUrl), {
    method: "GET",
    headers: propagateHeaders({
      Authorization: `Bearer ${params.bearerToken}`,
    }),
  });

  if (!response.ok) {
    return false;
  }

  const payload = (await response.json()) as { teacher_id?: string };
  return payload.teacher_id === params.actorUserId;
}
