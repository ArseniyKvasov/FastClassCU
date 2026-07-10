/** Ported verbatim from core/templates/core/pages/landing/_features_section.html */
export function Features() {
  return (
    <section className="fc-section">
      <h2 className="fc-section-title">Всё, что нужно для эффективного урока</h2>
      <div className="row g-3 g-lg-4">
        <div className="col-lg-4 col-sm-6">
          <div className="fc-card fc-feature-card">
            <div className="fc-feature-icon purple">
              <i className="bi bi-pencil"></i>
            </div>
            <div className="fc-feature-title">
              Рисуй поверх <br />
              PDF и изображений
            </div>
            <p className="fc-feature-text">Выделяй, пиши и стирай - как на настоящей доске</p>
          </div>
        </div>
        <div className="col-lg-4 col-sm-6">
          <div className="fc-card fc-feature-card">
            <div className="fc-feature-icon green">
              <i className="bi bi-people"></i>
            </div>
            <div className="fc-feature-title">
              Взаимодействуйте <br />в реальном времени
            </div>
            <p className="fc-feature-text">Выполняйте задания с учеником даже без демонстрации экрана</p>
          </div>
        </div>
        <div className="col-lg-4">
          <div className="fc-card fc-feature-card">
            <div className="fc-feature-icon blue">
              <i className="bi bi-chat-dots"></i>
            </div>
            <div className="fc-feature-title">
              Чат и видеозвонок <br />
              внутри класса
            </div>
            <p className="fc-feature-text">Общайтесь и объясняйте материал без сторонних сервисов</p>
          </div>
        </div>
      </div>
    </section>
  );
}
