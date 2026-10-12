import { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import TrendCard from '../components/trends/TrendCard';
import CategoryHero from '../components/category/CategoryHero';
import FiltersPanel from '../components/category/FiltersPanel';
import { CATEGORY_THEMES, themeWash } from '../components/category/categoryThemes';
import { CATEGORIES, getTrendsByCategory } from '../mocks/mockData';
import './CategoryPage.css';

function sortItems(items, sort) 
{
  const list = [...items];
  if (sort === 'new') return list.sort((a, b) => a.weeks - b.weeks);
  if (sort === 'rising') return list.sort((a, b) => (b.prevRank - b.rank) - (a.prevRank - a.rank));
  return list.sort((a, b) => a.rank - b.rank);
}

function CategoryView({ category }) {
  const navigate = useNavigate();
  const theme = CATEGORY_THEMES[category.id];

  const [sort, setSort] = useState('popular');
  const [selectedGenres, setSelectedGenres] = useState([]);

  const toggleGenre = (g) =>
    setSelectedGenres((prev) =>
      prev.includes(g) ? prev.filter((x) => x !== g) : [...prev, g]
    );

  const items = useMemo(() => {
    const all = getTrendsByCategory(category.id);
    const filtered = selectedGenres.length
      ? all.filter((i) => selectedGenres.includes(i.genre))
      : all;
    return sortItems(filtered, sort);
  }, [category.id, sort, selectedGenres]);

  return (
    <div className="category-page" style={{ background: themeWash(theme) }}>
      <div className="category-content">
        <CategoryHero
          label={category.label}
          theme={theme}
          period="Неделя: 15–21 сентября"
        />

        <div className="cat-body">
          <FiltersPanel
            sort={sort}
            onSortChange={setSort}
            genres={category.genres}
            selectedGenres={selectedGenres}
            onGenreToggle={toggleGenre}
            onReset={() => setSelectedGenres([])}
          />

          <div className="category-list">
            {items.length === 0 && (
              <div className="category-empty">В этих жанрах пока ничего нет</div>
            )}
            {items.map((item) => (
              <TrendCard
                key={item.key}
                item={item}
                onClick={() => navigate(`/trend/${item.key}`)}
              />
            ))}
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