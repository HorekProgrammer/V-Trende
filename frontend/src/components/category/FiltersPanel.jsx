import SortChips from './SortChips';
import GenreFilter from './GenreFilter';
import './FiltersPanel.css';

export default function FiltersPanel
({
  sort,
  onSortChange,
  genres,
  selectedGenres,
  onGenreToggle,
  onReset,
}) {
    return (
    <aside className="filters">
      <div className="filter-group">
        <div className="filter-label">СОРТИРОВКА</div>
        <SortChips value={sort} onChange={onSortChange} />
      </div>

      {genres.length > 0 && (
        <div className="filter-group">
          <div className="filter-label">ЖАНР</div>
          <GenreFilter genres={genres} selected={selectedGenres} onToggle={onGenreToggle} />
          {selectedGenres.length > 0 && (
            <button type="button" className="filters-reset" onClick={onReset}>
              Сбросить жанры
            </button>
          )}
        </div>
      )}
    </aside>
  );
}