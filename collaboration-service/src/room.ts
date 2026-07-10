import { createHash } from "node:crypto";

import type { SessionRequest } from "./types.js";

export const ROOM_PREFIX = "writing-answer";

export function buildRoomId(input: SessionRequest): string {
  const raw = [
    input.task_id,
    input.context_type,
    input.context_id,
    input.owner_user_id,
  ].join(":");
  const digest = createHash("sha256").update(raw).digest("hex");
  return `${ROOM_PREFIX}:${digest}`;
}
