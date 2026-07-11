import englishCard from "../../legacy/images/home/present-continuous-lesson-card.webp";
import clothesCard from "../../legacy/images/home/clothes-lesson-card.webp";
import environmentCard from "../../legacy/images/home/environmental-lesson-card.webp";

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
            onClick={() => onPreview(clothesCard, "Карточка урока: Clothes")}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onPreview(clothesCard, "Карточка урока: Clothes");
              }
            }}
          >
            <div className="fc-example-title">Clothes</div>
            <div className="fc-example-count">10 заданий</div>
            <img src={clothesCard} alt="Карточка урока" className="fc-example-preview" />
          </div>
        </div>

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
            <div className="fc-example-title">Present Continuous</div>
            <div className="fc-example-count">12 заданий</div>
            <img src={englishCard} alt="Карточка урока" className="fc-example-preview" />
          </div>
        </div>

        <div className="col-lg-4">
          <div
            className="fc-card fc-example-card js-lesson-preview-card"
            role="button"
            tabIndex={0}
            onClick={() => onPreview(environmentCard, "Карточка урока: Environment")}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onPreview(environmentCard, "Карточка урока: Environment");
              }
            }}
          >
            <div className="fc-example-title">Environment</div>
            <div className="fc-example-count">14 заданий</div>
            <img src={environmentCard} alt="Карточка урока" className="fc-example-preview" />
          </div>
        </div>
      </div>
    </section>
  );
}
