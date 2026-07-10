import heroBookPencil from "../../legacy/images/home/hero-book-pencil.png";
import singlePage from "../../legacy/images/home/fastclass-single-page.png";

interface CompareProps {
  onPreview: (src: string, alt: string) => void;
}

/** Ported verbatim from core/templates/core/pages/landing/_compare_section.html */
export function Compare({ onPreview }: CompareProps) {
  return (
    <section className="fc-section">
      <h2 className="fc-section-title">Почему FastClass удобнее обычного онлайн-урока</h2>
      <div className="row g-3 g-lg-4 align-items-stretch">
        <div className="col-lg-6">
          <div className="fc-card fc-compare-card bad">
            <div className="fc-compare-title">
              <span className="fc-compare-icon bad">
                <i className="bi bi-x-lg"></i>
              </span>
              <span>Обычный онлайн-урок</span>
            </div>

            <div className="fc-chaos">
              <div className="fc-chaos-window">
                <div className="fc-chaos-bar">
                  <span className="fc-chaos-dot"></span>
                  <span className="fc-chaos-dot"></span>
                  <span className="fc-chaos-dot"></span>
                </div>
                <div className="fc-chaos-window-title">Zoom</div>
                <div className="fc-chaos-video-grid">
                  <div className="fc-chaos-video-cell"></div>
                  <div className="fc-chaos-video-cell"></div>
                  <div className="fc-chaos-video-cell"></div>
                  <div className="fc-chaos-video-cell"></div>
                </div>
              </div>
              <div className="fc-chaos-window">
                <div className="fc-chaos-bar">
                  <span className="fc-chaos-dot"></span>
                  <span className="fc-chaos-dot"></span>
                  <span className="fc-chaos-dot"></span>
                </div>
                <div className="fc-chaos-window-title">PDF</div>
                <div className="fc-chaos-pdf-icon">
                  <i className="bi bi-file-earmark-pdf-fill"></i>
                </div>
              </div>
              <div className="fc-chaos-window">
                <div className="fc-chaos-bar">
                  <span className="fc-chaos-dot"></span>
                  <span className="fc-chaos-dot"></span>
                  <span className="fc-chaos-dot"></span>
                </div>
                <div className="fc-chaos-window-title">Доска</div>
                <div className="fc-chaos-board"></div>
              </div>
              <div className="fc-chaos-window">
                <div className="fc-chaos-bar">
                  <span className="fc-chaos-dot"></span>
                  <span className="fc-chaos-dot"></span>
                  <span className="fc-chaos-dot"></span>
                </div>
                <div className="fc-chaos-window-title">Чат</div>
                <div className="fc-chaos-chat-line"></div>
                <div className="fc-chaos-chat-line w-75"></div>
                <div className="fc-chaos-chat-line w-50 mb-0"></div>
              </div>
            </div>

            <ul className="fc-list">
              <li>
                <span className="fc-list-mark bad">
                  <i className="bi bi-x-lg"></i>
                </span>
                <span>Zoom + PDF + доска + чат</span>
              </li>
              <li>
                <span className="fc-list-mark bad">
                  <i className="bi bi-x-lg"></i>
                </span>
                <span>Постоянные переключения</span>
              </li>
              <li>
                <span className="fc-list-mark bad">
                  <i className="bi bi-x-lg"></i>
                </span>
                <span>Теряется внимание</span>
              </li>
            </ul>
          </div>
        </div>

        <div className="col-lg-6">
          <div
            className="fc-card fc-compare-card good js-lesson-preview-card"
            role="button"
            tabIndex={0}
            onClick={() => onPreview(singlePage, "Фото урока в FastClass")}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onPreview(singlePage, "Фото урока в FastClass");
              }
            }}
          >
            <img src={heroBookPencil} alt="" aria-hidden="true" className="fc-compare-book-image" />
            <div className="fc-compare-title">
              <span className="fc-compare-icon good">
                <i className="bi bi-check-lg"></i>
              </span>
              <span>Урок в FastClass</span>
            </div>

            <div className="fc-mini-screen">
              <img src={singlePage} alt="FastClass Single Screen" />
            </div>

            <ul className="fc-list">
              <li>
                <span className="fc-list-mark good">
                  <i className="bi bi-check-lg"></i>
                </span>
                <span>Всё в одном окне</span>
              </li>
              <li>
                <span className="fc-list-mark good">
                  <i className="bi bi-check-lg"></i>
                </span>
                <span>Урок уже готов</span>
              </li>
              <li>
                <span className="fc-list-mark good">
                  <i className="bi bi-check-lg"></i>
                </span>
                <span>Ученик подключается по ссылке</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
