import { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import TrendCard from '../components/trends/TrendCard';
import CategoryHero from '../components/category/CategoryHero';
import FiltersPanel from '../components/category/FiltersPanel';
import DataState from '../components/common/DataState';
import { CATEGORY_THEMES, themeWash } from '../components/category/categoryThemes';
import { CATEGORIES } from '../components/category/categories';
import { useApi } from '../api/useApi';
import { categoryTrendsPath } from '../api/paths';
import { formatWeek } from '../utils/dates';
import './CategoryPage.css';

function CategoryView({ category }) {
  const navigate = useNavigate();
  const theme = CATEGORY_THEMES[category.id];

  const [sort, setSort] = useState('popular');
  const [selectedGenres, setSelectedGenres] = useState([]);

  const { data, loading, error } = useApi(categoryTrendsPath(category.id, sort));

  const allItems = useMemo(() => (data ? data.items : []), [data]);

  const genreOptions = useMemo(
    () =>
      [...new Set(allItems.map((i) => i.genre).filter(Boolean))].sort((a, b) =>
        a.localeCompare(b, 'ru')
      ),
    [allItems]
  );

  const items = selectedGenres.length
    ? allItems.filter((i) => selectedGenres.includes(i.genre))
    : allItems;

  const toggleGenre = (g) =>
    setSelectedGenres((prev) =>
      prev.includes(g) ? prev.filter((x) => x !== g) : [...prev, g]
    );

  const period = data?.weekStart ? `Неделя: ${formatWeek(data.weekStart)}` : '';

  return (
    <div className="category-page" style={{ background: themeWash(theme) }}>
      <div className="category-content">
        <CategoryHero label={category.label} theme={theme} period={period} />

        <div className="cat-body">
          <FiltersPanel
            sort={sort}
            onSortChange={setSort}
            genres={genreOptions}
            selectedGenres={selectedGenres}
            onGenreToggle={toggleGenre}
            onReset={() => setSelectedGenres([])}
          />

          <div className={`category-list ${loading && data ? 'is-loading' : ''}`}>
            <DataState loading={loading && !data} error={error}>
              {data && items.length === 0 && (
                <div className="category-empty">
                  {selectedGenres.length
                    ? 'В этих жанрах пока ничего нет'
                    : 'В этой категории пока нет данных'}
                </div>
              )}
              {items.map((item) => (
                <TrendCard
                  key={item.key}
                  item={item}
                  onClick={() => navigate(`/trend/${item.key}`)}
                />
              ))}
            </DataState>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function CategoryPage() {
  const { name } = useParams();
  const category = CATEGORIES.find((c) => c.id === name);

  if (!category) {
    return (
      <div className="category-content">
        <p>Категория не найдена</p>
      </div>
    );
  }

  return <CategoryView key={category.id} category={category} />;
}