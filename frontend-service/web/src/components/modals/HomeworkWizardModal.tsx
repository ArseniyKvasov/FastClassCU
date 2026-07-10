import { useEffect, useMemo, useRef, useState } from "react";
import { Modal } from "bootstrap";
import {
  isWeightEligible,
  lessonsApi,
  taskCountLabel,
  TASK_TYPE_LABELS,
  taskPreviewText,
  type LessonBundleSection,
  type LessonListItemOut,
} from "../../lib/lessons";
import { assignmentsApi } from "../../lib/assignments";
import { useToast } from "../Toast";
import { DeadlinePicker } from "./DeadlinePicker";

interface HomeworkWizardModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type Step = 1 | 2 | 3 | 4;

const DERIVATION_LABELS: Record<LessonListItemOut["derivation_type"], string> = {
  original: "Ваш урок",
  clone: "Клон",
  copy: "Копия",
};

/**
 * Three steps, per spec:
 * 1) choose lesson  2) choose tasks + grade weight  3) deadline + limits,
 * then issue.
 *
 * Copy-on-write handling: step 2 always reads the *selected* lesson's own
 * bundle directly - if that lesson is a clone, this is the clone's live
 * content, not a copy (no copy is made just to browse). Only when the
 * wizard actually commits (step 3 submit) does a clone get converted to an
 * owned copy via the idempotent POST /lessons/{id}/copy - which returns the
 * user's existing copy if they already made one, or creates it now. Because
 * a copy duplicates structural section/task rows (new ids) while sharing
 * immutable content by pointer, the selected task ids (and their weights)
 * from the clone's bundle are not valid against the copy; we translate the
 * selection by (section position, task position) instead of by id.
 */
export function HomeworkWizardModal({ isOpen, onClose }: HomeworkWizardModalProps) {
  const elRef = useRef<HTMLDivElement>(null);
  const modalRef = useRef<Modal | null>(null);
  const { show } = useToast();

  const [step, setStep] = useState<Step>(1);
  const [lessons, setLessons] = useState<LessonListItemOut[] | null>(null);
  const [lessonsError, setLessonsError] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedLesson, setSelectedLesson] = useState<LessonListItemOut | null>(null);

  const [bundle, setBundle] = useState<LessonBundleSection[] | null>(null);
  const [bundleError, setBundleError] = useState(false);
  const [openSections, setOpenSections] = useState<Set<string>>(new Set());
  const [selectedTaskIds, setSelectedTaskIds] = useState<Set<string>>(new Set());
  const [weightInputs, setWeightInputs] = useState<Record<string, string>>({});

  const [title, setTitle] = useState("");
  const [deadline, setDeadline] = useState("");
  const [timeLimit, setTimeLimit] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [resultLink, setResultLink] = useState<string | null>(null);

  useEffect(() => {
    const el = elRef.current;
    if (!el) return;
    const modal = new Modal(el);
    modalRef.current = modal;
    const onHidden = () => onClose();
    el.addEventListener("hidden.bs.modal", onHidden);
    return () => {
      el.removeEventListener("hidden.bs.modal", onHidden);
      modal.dispose();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (isOpen) {
      modalRef.current?.show();
    } else {
      modalRef.current?.hide();
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    setStep(1);
    setSelectedLesson(null);
    setBundle(null);
    setSelectedTaskIds(new Set());
    setWeightInputs({});
    setTitle("");
    setDeadline("");
    setTimeLimit("");
    setSubmitError(null);
    setResultLink(null);
    setLessonsError(false);
    lessonsApi
      .listMine()
      .then(setLessons)
      .catch(() => setLessonsError(true));
  }, [isOpen]);

  const filteredLessons = useMemo(() => {
    if (!lessons) return [];
    const term = search.trim().toLowerCase();
    if (!term) return lessons;
    return lessons.filter((lesson) => lesson.title.toLowerCase().includes(term));
  }, [lessons, search]);

  const selectLesson = async (lesson: LessonListItemOut) => {
    setSelectedLesson(lesson);
    setTitle(lesson.title);
    setBundle(null);
    setBundleError(false);
    setSelectedTaskIds(new Set());
    setWeightInputs({});
    setStep(2);
    try {
      const loaded = await lessonsApi.getBundle(lesson.id);
      setBundle(loaded);
      setOpenSections(new Set(loaded.length ? [loaded[0].section.id] : []));
    } catch {
      setBundleError(true);
    }
  };

  const deselectTask = (taskId: string) => {
    setWeightInputs((prev) => {
      const next = { ...prev };
      delete next[taskId];
      return next;
    });
  };

  const toggleTask = (taskId: string) => {
    setSelectedTaskIds((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) {
        next.delete(taskId);
        deselectTask(taskId);
      } else {
        next.add(taskId);
      }
      return next;
    });
  };

  const toggleSectionAll = (section: LessonBundleSection) => {
    const ids = section.tasks.map((t) => t.id);
    const allSelected = ids.every((id) => selectedTaskIds.has(id));
    setSelectedTaskIds((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => (allSelected ? next.delete(id) : next.add(id)));
      return next;
    });
    if (allSelected) ids.forEach(deselectTask);
  };

  const toggleSectionOpen = (sectionId: string) => {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(sectionId)) next.delete(sectionId);
      else next.add(sectionId);
      return next;
    });
  };

  const remainingWeightExcluding = (excludeTaskId: string): number => {
    let used = 0;
    selectedTaskIds.forEach((id) => {
      if (id === excludeTaskId) return;
      const parsed = parseFloat((weightInputs[id] ?? "").replace(",", "."));
      if (!isNaN(parsed) && parsed > 0) used += parsed;
    });
    return Math.max(0, 100 - used);
  };

  const handleWeightInput = (taskId: string, raw: string) => {
    let val = raw.replace(/[^0-9.,]/g, "");
    const sepIndex = val.search(/[.,]/);
    if (sepIndex !== -1) {
      val = val.slice(0, sepIndex + 1) + val.slice(sepIndex + 1).replace(/[.,]/g, "");
    }
    setWeightInputs((prev) => ({ ...prev, [taskId]: val }));
  };

  const handleWeightBlur = (taskId: string) => {
    const raw = weightInputs[taskId] ?? "";
    if (raw.trim() === "") return;
    const numeric = parseFloat(raw.replace(",", "."));
    if (isNaN(numeric)) {
      setWeightInputs((prev) => ({ ...prev, [taskId]: "" }));
      return;
    }
    const max = remainingWeightExcluding(taskId);
    let clamped = Math.min(Math.max(numeric, 0), max);
    clamped = Math.round(clamped * 10) / 10;
    setWeightInputs((prev) => ({ ...prev, [taskId]: clamped <= 0 ? "" : String(clamped) }));
  };

  const selectedCount = selectedTaskIds.size;

  const handleSubmit = async () => {
    if (!selectedLesson || !bundle) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      // Record selection (+ weight) as (sectionIndex, taskIndex) pairs
      // before any lesson-id swap, so it survives translating clone ids ->
      // copy ids.
      const positions: { sectionIdx: number; taskIdx: number; weight: number | null }[] = [];
      bundle.forEach((section, sectionIdx) => {
        section.tasks.forEach((task, taskIdx) => {
          if (!selectedTaskIds.has(task.id)) return;
          const parsed = parseFloat((weightInputs[task.id] ?? "").replace(",", "."));
          positions.push({
            sectionIdx,
            taskIdx,
            weight: !isNaN(parsed) && parsed > 0 ? parsed : null,
          });
        });
      });

      let finalLessonId = selectedLesson.id;
      let finalBundle = bundle;
      if (selectedLesson.derivation_type === "clone") {
        const copy = await lessonsApi.copy(selectedLesson.id);
        finalLessonId = copy.id;
        finalBundle = await lessonsApi.getBundle(copy.id);
      }

      const finalTasks = positions
        .map((p) => {
          const id = finalBundle[p.sectionIdx]?.tasks[p.taskIdx]?.id;
          return id ? { task_id: id, weight: p.weight } : null;
        })
        .filter((t): t is { task_id: string; weight: number | null } => t !== null);

      if (!finalTasks.length) {
        throw new Error("no_tasks_after_translation");
      }

      const assignment = await assignmentsApi.create({
        title: title.trim() || selectedLesson.title,
        lesson_id: finalLessonId,
        deadline: deadline || null,
        time_limit_minutes: timeLimit ? Number(timeLimit) : null,
        target_type: "link",
        tasks: finalTasks,
      });

      setResultLink(`${window.location.origin}/assignments/${assignment.id}`);
      setStep(4);
    } catch {
      setSubmitError("Не удалось выдать задание. Попробуйте снова.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDone = () => {
    show("Задание выдано", "success");
    modalRef.current?.hide();
  };

  return (
    <div className="modal fade" tabIndex={-1} aria-hidden="true" ref={elRef}>
      <div className="modal-dialog modal-dialog-centered hw-modal-dialog">
        <div className="modal-content hw-modal">
          <div className="modal-header hw-modal-header">
            <div className="hw-modal-title-group">
              {step > 1 && step < 4 ? (
                <button type="button" className="hw-modal-back" onClick={() => setStep((step - 1) as Step)}>
                  <i className="bi bi-arrow-left"></i>
                </button>
              ) : null}
              <div className="hw-modal-header-text">
                <h5 className="hw-modal-title">
                  {step === 1 && "Выбор урока"}
                  {step === 2 && "Выбор заданий"}
                  {step === 3 && "Дедлайн и ограничения"}
                  {step === 4 && "Задание готово"}
                </h5>
              </div>
            </div>
            <button type="button" className="hw-modal-close" data-bs-dismiss="modal" aria-label="Закрыть">
              <i className="bi bi-x-lg"></i>
            </button>
          </div>

          <div className="modal-body hw-modal-body">
            {step === 1 ? (
              <div className="hw-step">
                <div className="hw-search-group">
                  <i className="bi bi-search"></i>
                  <input
                    type="text"
                    placeholder="Поиск урока..."
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                  />
                </div>
                <div className="hw-lessons-list">
                  {lessonsError ? (
                    <div className="hw-empty-state text-danger">Не удалось загрузить уроки.</div>
                  ) : lessons === null ? (
                    <div className="hw-empty-state">
                      <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                    </div>
                  ) : filteredLessons.length === 0 ? (
                    <div className="hw-empty-state">Ничего не найдено</div>
                  ) : (
                    filteredLessons.map((lesson) => {
                      const metaParts = [taskCountLabel(lesson.task_count), DERIVATION_LABELS[lesson.derivation_type]];
                      return (
                        <div
                          key={lesson.id}
                          className={`hw-lesson-row ${selectedLesson?.id === lesson.id ? "selected" : ""}`}
                          role="button"
                          tabIndex={0}
                          onClick={() => selectLesson(lesson)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              selectLesson(lesson);
                            }
                          }}
                        >
                          <span className="hw-lesson-icon">
                            <i
                              className={`bi ${lesson.derivation_type === "original" ? "bi-journal-text" : "bi-diagram-3"}`}
                            ></i>
                          </span>
                          <div className="flex-grow-1 min-w-0">
                            <div className="hw-lesson-row-name text-truncate">{lesson.title}</div>
                            <div className="hw-lesson-row-meta d-flex flex-wrap align-items-center" style={{ gap: 2 }}>
                              {metaParts.map((part, idx) => (
                                <span key={idx} className="d-flex align-items-center">
                                  {idx > 0 ? <span className="px-1 text-muted opacity-50">&middot;</span> : null}
                                  {part}
                                </span>
                              ))}
                            </div>
                          </div>
                          <i className="bi bi-chevron-right text-muted"></i>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            ) : null}

            {step === 2 ? (
              <div className="hw-step">
                {bundleError ? (
                  <div className="hw-empty-state text-danger">Не удалось загрузить задания урока.</div>
                ) : bundle === null ? (
                  <div className="hw-empty-state">
                    <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                  </div>
                ) : bundle.every((s) => s.tasks.length === 0) ? (
                  <div className="hw-empty-state">Этот урок не содержит заданий</div>
                ) : (
                  <div className="hw-lesson-sheet">
                    {bundle
                      .filter((section) => section.tasks.length > 0)
                      .map((section) => {
                        const ids = section.tasks.map((t) => t.id);
                        const selectedInSection = ids.filter((id) => selectedTaskIds.has(id)).length;
                        const state =
                          selectedInSection === 0
                            ? ""
                            : selectedInSection === ids.length
                              ? "checked"
                              : "indeterminate";
                        const isOpenSection = openSections.has(section.section.id);
                        return (
                          <div
                            key={section.section.id}
                            className={`hw-section-card ${isOpenSection ? "is-open" : ""}`}
                          >
                            <div className="hw-section-header" onClick={() => toggleSectionOpen(section.section.id)}>
                              <span
                                className={`hw-tristate-check ${state}`}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  toggleSectionAll(section);
                                }}
                              >
                                <i className="bi bi-check-lg"></i>
                                <i className="bi bi-dash-lg"></i>
                              </span>
                              <span className="hw-section-title">{section.section.title || "Без названия"}</span>
                              <span className="hw-section-count">
                                {selectedInSection}/{ids.length}
                              </span>
                              <i className="bi bi-chevron-down hw-section-arrow"></i>
                            </div>
                            <div className="hw-section-tasks">
                              {section.tasks.map((task) => {
                                const selected = selectedTaskIds.has(task.id);
                                const eligible = isWeightEligible(task.task_type);
                                const preview = taskPreviewText(task);
                                return (
                                  <div key={task.id} className={`hw-task-card ${selected ? "selected" : ""}`}>
                                    <div className="hw-task-preview-wrap">
                                      {preview ? (
                                        <div className="hw-task-card-preview">{preview}</div>
                                      ) : (
                                        <div className="hw-task-card-preview hw-task-fallback">
                                          {TASK_TYPE_LABELS[task.task_type] ?? task.task_type}
                                        </div>
                                      )}
                                      <button
                                        type="button"
                                        className="hw-task-select-btn"
                                        onClick={() => toggleTask(task.id)}
                                      >
                                        <span className="hw-task-select-pill">
                                          <i className={`bi ${selected ? "bi-check-lg" : "bi-plus-lg"}`}></i>
                                          {selected ? "Выбрано" : "Выбрать"}
                                        </span>
                                      </button>
                                    </div>
                                    <div className={`hw-task-weight ${eligible ? "is-eligible" : ""}`}>
                                      <label>Вес задания в оценке</label>
                                      <div className="hw-weight-input-wrap">
                                        <input
                                          type="text"
                                          inputMode="decimal"
                                          placeholder="auto"
                                          value={weightInputs[task.id] ?? ""}
                                          onClick={(event) => event.stopPropagation()}
                                          onChange={(event) => handleWeightInput(task.id, event.target.value)}
                                          onBlur={() => handleWeightBlur(task.id)}
                                        />
                                        <span>%</span>
                                      </div>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        );
                      })}
                  </div>
                )}
                <div className="hw-step2-footer">
                  <button
                    type="button"
                    className="hw-issue-btn"
                    disabled={selectedCount === 0}
                    onClick={() => setStep(3)}
                  >
                    Далее{selectedCount > 0 ? ` (${selectedCount})` : ""}
                  </button>
                </div>
              </div>
            ) : null}

            {step === 3 ? (
              <div className="hw-step">
                <div className="hw-settings-grid">
                  <div className="hw-field hw-field-full">
                    <label htmlFor="hwTitle">Название</label>
                    <input
                      id="hwTitle"
                      type="text"
                      maxLength={60}
                      value={title}
                      onChange={(event) => setTitle(event.target.value)}
                      placeholder="Домашнее задание"
                    />
                  </div>
                  <div className="hw-field hw-deadline-field">
                    <label>Дедлайн</label>
                    <DeadlinePicker value={deadline} onChange={setDeadline} />
                  </div>
                  <div className="hw-field">
                    <label htmlFor="hwTimeLimit">Время на выполнение, мин</label>
                    <input
                      id="hwTimeLimit"
                      type="number"
                      min={1}
                      inputMode="numeric"
                      value={timeLimit}
                      onChange={(event) => setTimeLimit(event.target.value)}
                      placeholder="Без ограничения"
                    />
                  </div>
                </div>
                {submitError ? <p className="text-danger small mt-3 mb-0">{submitError}</p> : null}
                <div className="hw-step2-footer">
                  <button type="button" className="hw-issue-btn" disabled={submitting} onClick={handleSubmit}>
                    {submitting ? (
                      <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                    ) : null}
                    Выдать задание
                  </button>
                </div>
              </div>
            ) : null}

            {step === 4 && resultLink ? (
              <div className="hw-result-panel">
                <div className="hw-link-group">
                  <input type="text" readOnly value={resultLink} />
                  <button
                    type="button"
                    title="Копировать ссылку"
                    onClick={() => {
                      navigator.clipboard.writeText(resultLink);
                      show("Ссылка скопирована", "success");
                    }}
                  >
                    <i className="bi bi-copy"></i>
                  </button>
                </div>
                <button type="button" className="hw-issue-btn" onClick={handleDone}>
                  Готово
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
