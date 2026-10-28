import './DataState.css';

export default function DataState({ loading, error, children }) 
{
  if (loading) return <div className="data-state">Загрузка…</div>;
  if (error) 
  {
    return (
      <div className="data-state data-state--error">
        Не удалось загрузить данные. Попробуйте обновить страницу.
      </div>
    );
  }
  return children;
}