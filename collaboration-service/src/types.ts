import type { JSONContent } from "@tiptap/core";
import type {
  AnswersSnapshot,
  ContextType,
  SessionContext,
  SessionRequest,
} from "@fastclass/node-shared";

export type { AnswersSnapshot, ContextType, SessionContext, SessionRequest };

export interface AuthUser {
  userId: string;
  accessLevel: string;
  rawToken: string;
}

export interface CollabTokenClaims extends SessionRequest {
  room_id: string;
  actor_user_id: string;
  actor_role: "owner" | "teacher";
  iss: string;
  sub: string;
  iat: number;
  exp: number;
}

export interface StoredDocumentRow {
  room_id: string;
  task_id: string;
  context_type: ContextType;
  context_id: string;
  owner_user_id: string;
  yjs_state: Buffer;
  revision: number;
  schema_version: number;
}

export interface PersistedSnapshot {
  revision: number;
  documentJson: JSONContent;
  plainText: string;
}
