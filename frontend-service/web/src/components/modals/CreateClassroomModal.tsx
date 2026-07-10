import { useEffect, useRef, useState } from "react";
import { Modal } from "bootstrap";
import { classroomsApi, type ClassroomCreatedOut } from "../../lib/classrooms";
import { useToast } from "../Toast";

interface CreateClassroomModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated?: (classroom: ClassroomCreatedOut) => void;
}

export function CreateClassroomModal({ isOpen, onClose, onCreated }: CreateClassroomModalProps) {
  const elRef = useRef<HTMLDivElement>(null);
  const modalRef = useRef<Modal | null>(null);
  const { show } = useToast();

  const [title, setTitle] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ClassroomCreatedOut | null>(null);

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
    setTitle("");
    setError(null);
    setResult(null);
  }, [isOpen]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!title.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const classroom = await classroomsApi.create({ title: title.trim() });
      setResult(classroom);
      onCreated?.(classroom);
    } catch {
      setError("Не удалось создать класс. Попробуйте снова.");
    } finally {
      setSubmitting(false);
    }
  };

  const joinLink = result ? `${window.location.origin}/join/${result.id}` : "";

  return (
    <div className="modal fade" tabIndex={-1} aria-hidden="true" ref={elRef}>
      <div className="modal-dialog modal-dialog-centered hw-modal-dialog">
        <div className="modal-content hw-modal">
          <div className="modal-header hw-modal-header">
            <div className="hw-modal-header-text">
              <h5 className="hw-modal-title">{result ? "Класс создан" : "Создать класс"}</h5>
            </div>
            <button type="button" className="hw-modal-close" data-bs-dismiss="modal" aria-label="Закрыть">
              <i className="bi bi-x-lg"></i>
            </button>
          </div>

          <div className="modal-body hw-modal-body" style={{ minHeight: "auto" }}>
            {!result ? (
              <form className="hw-step" onSubmit={handleSubmit}>
                <div className="hw-settings-grid">
                  <div className="hw-field hw-field-full">
                    <label htmlFor="classroomTitle">Название класса</label>
                    <input
                      id="classroomTitle"
                      type="text"
                      maxLength={255}
                      autoFocus
                      value={title}
                      onChange={(event) => setTitle(event.target.value)}
                      placeholder="Например, 9 «А»"
                    />
                  </div>
                </div>
                {error ? <p className="text-danger small mt-3 mb-0">{error}</p> : null}
                <div className="hw-step2-footer">
                  <button type="submit" className="hw-issue-btn" disabled={submitting || !title.trim()}>
                    {submitting ? (
                      <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                    ) : null}
                    Создать
                  </button>
                </div>
              </form>
            ) : (
              <div className="hw-result-panel">
                <p className="text-muted small">
                  Пригласительная ссылка и пароль для входа - поделитесь ими с учениками.
                </p>
                <div className="hw-field hw-field-full mb-2">
                  <label>Ссылка</label>
                  <div className="hw-link-group">
                    <input type="text" readOnly value={joinLink} />
                    <button
                      type="button"
                      title="Копировать ссылку"
                      onClick={() => {
                        navigator.clipboard.writeText(joinLink);
                        show("Ссылка скопирована", "success");
                      }}
                    >
                      <i className="bi bi-copy"></i>
                    </button>
                  </div>
                </div>
                <div className="hw-field hw-field-full">
                  <label>Пароль для входа</label>
                  <div className="hw-link-group">
                    <input type="text" readOnly value={result.join_password} />
                    <button
                      type="button"
                      title="Копировать пароль"
                      onClick={() => {
                        navigator.clipboard.writeText(result.join_password);
                        show("Пароль скопирован", "success");
                      }}
                    >
                      <i className="bi bi-copy"></i>
                    </button>
                  </div>
                </div>
                <button type="button" className="hw-issue-btn mt-3" onClick={() => modalRef.current?.hide()}>
                  Готово
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
