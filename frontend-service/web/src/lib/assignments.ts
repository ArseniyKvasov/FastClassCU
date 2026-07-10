import { api } from "./apiClient";

export interface CreateAssignmentInput {
  title: string;
  lesson_id: string;
  deadline: string | null;
  time_limit_minutes: number | null;
  target_type: "link";
  tasks: { task_id: string; weight?: number | null }[];
}

export interface AssignmentOut {
  id: string;
  teacher_id: string;
  lesson_id: string;
  title: string;
  deadline: string | null;
  time_limit_minutes: number | null;
  target_type: string;
  created_at: string;
  tasks: { task_id: string; position: number; weight: number | null }[];
}

export const assignmentsApi = {
  create: (body: CreateAssignmentInput) => api.post<AssignmentOut>("/assignments", body),
};
