import englishCard from "../../legacy/images/home/english-lesson-card.png";
import mathCard from "../../legacy/images/home/math-lesson-card.png";
import socialCard from "../../legacy/images/home/social-studies-lesson-card.png";

interface ExamplesProps {
  onPreview: (src: string, alt: string) => void;
}

/** Ported verbatim from core/templates/core/pages/landing/_examples_section.html */
export function Examples({ onPreview }: ExamplesProps) {
  return (
    <section className="fc-section">
      <h2 className="fc-section-title">Готовые уроки, которые можно использовать сразу</h2>
      <div className="row g-3 g-lg-4">
        <div className="col-lg-4 col-sm-6">
          <div
            className="fc-card fc-example-card js-lesson-preview-card"
            role="button"
            tabIndex={0}
            onClick={() => onPreview(englishCard, "Карточка урока: Present Continuous")}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onPreview(englishCard, "Карточка урока: Present Continuous");
              }
            }}
          >
            <span className="fc-example-badge blue">Английский язык</span>
            <div className="fc-example-title">Present Continuous</div>
            <div className="fc-example-count">12 заданий</div>
            <img src={englishCard} alt="Карточка урока" className="fc-example-preview" />
          </div>
        </div>

        <div className="col-lg-4 col-sm-6">
          <div
            className="fc-card fc-example-card js-lesson-preview-card"
            role="button"
            tabIndex={0}
            onClick={() => onPreview(mathCard, "Карточка урока: Десятичные дроби")}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onPreview(mathCard, "Карточка урока: Десятичные дроби");
              }
            }}
          >
            <span className="fc-example-badge green">Математика</span>
            <div className="fc-example-title">Десятичные дроби</div>
            <div className="fc-example-count">10 заданий</div>
            <img src={mathCard} alt="Карточка урока" className="fc-example-preview" />
          </div>
        </div>

        <div className="col-lg-4">
          <div
            className="fc-card fc-example-card js-lesson-preview-card"
            role="button"
            tabIndex={0}
            onClick={() => onPreview(socialCard, "Карточка урока: Права граждан")}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onPreview(socialCard, "Карточка урока: Права граждан");
              }
            }}
          >
            <span className="fc-example-badge indigo">Обществознание</span>
            <div className="fc-example-title">Права граждан</div>
            <div className="fc-example-count">14 заданий</div>
            <img src={socialCard} alt="Карточка урока" className="fc-example-preview" />
          </div>
        </div>
      </div>
    </section>
  );
}
