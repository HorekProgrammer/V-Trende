import './FAQ.css';

const QUESTIONS =
[
  {
    question: 'Как высчитывается рейтинг?',
    answer: 'Мы изучаем статистику по всем российским сервисам статистики: от музыкальных стриминговых сервисов до количества запросов в интернете.'
  },
  {
    question: 'Какие формулы высчитывали рейтинга?',
    answer: 'Мы не разглашаем точные формулы. Мы берем разные источники и исходя из их влиятельности и популярности, высчитываем коэффициент умножения каждого источника.'
  },
  {
    question: 'Как мне попасть в рейтинг?',
    answer: 'Вы автоматически попадете в рейтинг, когда Вы или Ваш продукт станет популярным и поднимется высоко в чартах.'
  },
  {
    question: 'Как часто обновляется рейтинг?',
    answer: 'Рейтинг обновляется в полночь на понедельник каждую неделю по московскому времени.'
  }
];

export default function FAQ()
{
  return (
    <section className="faq">
      <h2 className="faq-title">Часто задаваемые вопросы</h2>

      <div className="faq-list">
        {QUESTIONS.map((item, index) => (
          <details className="faq-item" key={index}>
            <summary className="faq-question">
              <span>{item.question}</span>
              <span className="faq-icon"></span>
            </summary>

            <div className="faq-answer">
              {item.answer}
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}