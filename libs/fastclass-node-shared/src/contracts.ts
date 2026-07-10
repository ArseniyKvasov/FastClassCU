export type JsonContent = {
  type?: string;
  text?: string;
  content?: JsonContent[];
  [key: string]: unknown;
};

export type ContextType = "classroom" | "assignment";

export interface SessionRequest {
  task_id: string;
  context_type: ContextType;
  context_id: string;
  owner_user_id: string;
}

export interface SessionContext extends SessionRequest {
  roomId: string;
  actorUserId: string;
  actorRole: "owner" | "teacher";
}

export interface AnswersSnapshot {
  task_id: string;
  user_id: string;
  context_type: ContextType;
  context_id: string;
  document_json?: JsonContent | null;
  plain_text?: string | null;
  text?: string | null;
  revision?: number | null;
}
