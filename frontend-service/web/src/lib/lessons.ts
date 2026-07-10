import { api } from "./apiClient";

export type DerivationType = "original" | "clone" | "copy";

export interface LessonOut {
  id: string;
  owner_id: string;
  origin_lesson_id: string | null;
  derivation_type: DerivationType;
  title: string;
  description: string | null;
  is_public: boolean;
  created_at: string;
}

export interface LessonListItemOut extends LessonOut {
  task_count: number;
}

export interface SectionOut {
  id: string;
  lesson_id: string;
  title: string;
  position: number;
}

export interface TaskWithContentOut {
  id: string;
  section_id: string;
  task_type: string;
  current_content_id: string;
  position: number;
  payload: Record<string, unknown>;
}

export interface QuotaOut {
  teacher_id: string;
  storage_bytes: number;
  limit_bytes: number;
}

export interface LessonBundleSection {
  section: SectionOut;
  tasks: TaskWithContentOut[];
}

export const lessonsApi = {
  listMine: () => api.get<LessonListItemOut[]>("/lessons"),

  async getBundle(lessonId: string): Promise<LessonBundleSection[]> {
    const sections = await api.get<SectionOut[]>(`/lessons/${lessonId}/sections`);
    const withTasks = await Promise.all(
      sections
        .sort((a, b) => a.position - b.position)
        .map(async (section) => ({
          section,
          tasks: (await api.get<TaskWithContentOut[]>(`/sections/${section.id}/tasks`)).sort(
            (a, b) => a.position - b.position,
          ),
        })),
    );
    return withTasks;
  },

  copy: (lessonId: string) => api.post<LessonOut>(`/lessons/${lessonId}/copy`),

  getQuota: () => api.get<QuotaOut>("/quota"),
};

/** Ported from core/static/js/pages/homework_wizard.js's task-count pluralization. */
export function taskCountLabel(count: number): string {
  if (count === 0) return "Нет заданий";
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return `${count} задание`;
  if ([2, 3, 4].includes(mod10) && ![12, 13, 14].includes(mod100)) return `${count} задания`;
  return `${count} заданий`;
}

/** Ported from homework_wizard.js's NO_WEIGHT_TASK_TYPES - types with no
 * objective completion signal, so a numeric grade weight doesn't apply. */
const NO_WEIGHT_TASK_TYPES = new Set(["file", "text", "integration", "word_list"]);

export function isWeightEligible(taskType: string): boolean {
  return !NO_WEIGHT_TASK_TYPES.has(taskType);
}

export const TASK_TYPE_LABELS: Record<string, string> = {
  fill_gaps: "Заполнить пропуски",
  text: "Текст",
  writing_task: "Письменный ответ",
  true_false: "Правда или ложь",
  match_cards: "Сопоставление",
  reorder: "Порядок",
  sorting: "Сортировка",
  integration: "Интеграция",
  test: "Тест",
  file: "Файл",
  word_list: "Список слов",
  voice_recording: "Голосовая запись",
  image: "Изображение",
  audio: "Аудио",
};

export function taskPreviewText(task: TaskWithContentOut): string | null {
  const payload = task.payload as { content?: string; text?: string; question?: string };
  const text = payload?.content ?? payload?.text ?? payload?.question;
  if (typeof text === "string" && text.trim()) {
    return text.length > 140 ? `${text.slice(0, 140)}…` : text;
  }
  return null;
}
