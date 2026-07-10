import { api } from "./apiClient";

export interface CreateClassroomInput {
  title: string;
  lesson_id?: string | null;
}

export interface ClassroomCreatedOut {
  id: string;
  teacher_id: string;
  title: string;
  lesson_id: string | null;
  is_preview: boolean;
  created_at: string;
  join_password: string;
}

export const classroomsApi = {
  create: (body: CreateClassroomInput) => api.post<ClassroomCreatedOut>("/classrooms", body),
};
