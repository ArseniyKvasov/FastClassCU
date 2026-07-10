import { useState } from "react";
import { HomeworkWizardModal } from "../components/modals/HomeworkWizardModal";
import { CreateClassroomModal } from "../components/modals/CreateClassroomModal";
import "../legacy/css/main_page.css";

type Tab = "classrooms" | "assignments";

/** Ported verbatim from core/templates/core/pages/home.html */
export function Home() {
  const [tab, setTab] = useState<Tab>("classrooms");
  const [isCreateClassOpen, setCreateClassOpen] = useState(false);
  const [isHwWizardOpen, setHwWizardOpen] = useState(false);

  return (
    <div className="py-4 py-lg-5">
      <div className="container-xxl">
        <div className="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-3">
          <ul className="nav fc-segmented-tabs" role="tablist">
            <li className="nav-item" role="presentation">
              <button
                type="button"
                className={`nav-link ${tab === "classrooms" ? "active" : ""}`}
                role="tab"
                aria-selected={tab === "classrooms"}
                onClick={() => setTab("classrooms")}
              >
                <i className="bi bi-people-fill me-2"></i>Классы
              </button>
            </li>
            <li className="nav-item" role="presentation">
              <button
                type="button"
                className={`nav-link ${tab === "assignments" ? "active" : ""}`}
                role="tab"
                aria-selected={tab === "assignments"}
                onClick={() => setTab("assignments")}
              >
                <i className="bi bi-journal-check me-2"></i>Задания
              </button>
            </li>
          </ul>

          <div className="d-flex gap-2">
            <button
              type="button"
              className={`btn fc-btn-create-class ${tab === "classrooms" ? "" : "d-none"}`}
              onClick={() => setCreateClassOpen(true)}
            >
              <i className="bi bi-plus-lg"></i>
              <span className="d-none d-sm-inline">Создать класс</span>
            </button>
            <button
              type="button"
              className={`btn fc-btn-assign ${tab === "assignments" ? "" : "d-none"}`}
              onClick={() => setHwWizardOpen(true)}
            >
              <i className="bi bi-plus-lg"></i>
              <span className="d-none d-sm-inline">Выдать задание</span>
            </button>
          </div>
        </div>

        <div className="tab-content">
          <div className={`tab-pane fade ${tab === "classrooms" ? "show active" : ""}`} role="tabpanel">
            <div className="row g-3 g-lg-4">
              <div className="col-12">
                <div className="fc-empty-state">
                  <div className="fc-empty-state-icon">
                    <i className="bi bi-people-fill"></i>
                  </div>
                  <div className="fc-empty-state-title">У вас пока нет классов</div>
                  <div className="fc-empty-state-text">
                    Создайте класс и пригласите ученика по ссылке - это займёт меньше минуты.
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className={`tab-pane fade ${tab === "assignments" ? "show active" : ""}`} role="tabpanel">
            <div className="row g-3 g-lg-4">
              <div className="col-12">
                <div className="fc-empty-state">
                  <div className="fc-empty-state-icon">
                    <i className="bi bi-journal-check"></i>
                  </div>
                  <div className="fc-empty-state-title">У вас пока нет выданных заданий</div>
                  <div className="fc-empty-state-text">
                    Выдайте задание из готового урока - ученик откроет его по ссылке, без регистрации.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <CreateClassroomModal isOpen={isCreateClassOpen} onClose={() => setCreateClassOpen(false)} />
      <HomeworkWizardModal isOpen={isHwWizardOpen} onClose={() => setHwWizardOpen(false)} />
    </div>
  );
}
