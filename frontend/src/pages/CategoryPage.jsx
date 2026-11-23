import { useState, useMemo, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import TrendCard from '../components/trends/TrendCard';
import CategoryHero from '../components/category/CategoryHero';
import FiltersPanel from '../components/category/FiltersPanel';
import DataState from '../components/common/DataState';
import WeekSwitcher from '../components/common/WeekSwitcher';
import FAQ from '../components/common/FAQ';
import { CATEGORY_THEMES, themeWash } from '../components/category/categoryThemes';
import { CATEGORIES } from '../components/category/categories';
import { useApi } from '../api/useApi';
import { categoryTrendsPath, weeksPath } from '../api/paths';
import { useWeek } from '../api/useWeek';
import { formatWeek } from '../utils/dates';
import { setPageMetadata } from '../utils/seo';
import './CategoryPage.css';

function CategoryView({ category }) {
  const navigate = useNavigate();
  const theme = CATEGORY_THEMES[category.id];

  const [sort, setSort] = useState('popular');
  const [selectedGenres, setSelectedGenres] = useState([]);

  useEffect(() => {
    const metadata = {
      music: {
        title: 'Популярные песни — музыкальный чарт недели | В ЧАРТЕ',
        description: 'Музыкальный чарт недели: популярные песни и треки по данным музыкальных сервисов. Текущие позиции, изменения и история рейтинга.',
      },
      movies: {
        title: 'Топ фильмов недели — рейтинг популярности | В ЧАРТЕ',
        description: 'Топ популярных фильмов за неделю по данным Кинопоиска и зрительского интереса. Текущие позиции, изменения и история рейтинга.',
      },
      games: {
        title: 'Топ игр недели — рейтинг популярных игр | В ЧАРТЕ',
        description: 'Топ популярных игр за неделю по данным магазинных чартов и зрительской аудитории. Текущие позиции, изменения и история рейтинга.',
      },
      streamers: {
        title: 'Топ стримеров недели — рейтинг популярных стримеров | В ЧАРТЕ',
        description: 'Топ русскоязычных стримеров за неделю по статистике TwitchTracker и поисковому интересу. Позиции, изменения и история рейтинга.',
      },
    };
    setPageMetadata({ ...metadata[category.id], path: `/category/${category.id}` });
  }, [category.id]);
  const [week, setWeek] = useWeek();
  const { data: weeks } = useApi(weeksPath());
  const { data, loading, error } = useApi(categoryTrendsPath(category.id, sort, week));

  const allItems = useMemo(() => (data ? data.items : []), [data]);

  const genreOptions = useMemo(
    () =>
      [...new Set(allItems.flatMap((i) => i.genres?.length ? i.genres : [i.genre]).filter(Boolean))].sort((a, b) =>
        a.localeCompare(b, 'ru')
      ),
    [allItems]
  );

  const items = selectedGenres.length
    ? allItems.filter((i) => (i.genres?.length ? i.genres : [i.genre])
        .some((genre) => selectedGenres.includes(genre)))
    : allItems;

  const toggleGenre = (g) =>
    setSelectedGenres((prev) =>
      prev.includes(g) ? prev.filter((x) => x !== g) : [...prev, g]
    );

  const period = data?.weekStart ? `Неделя: ${formatWeek(data.weekStart)}` : '';
  const weekControl = weeks ? <WeekSwitcher weeks={weeks} value={week} onChange={setWeek} /> : null;

  return (
    <div className="category-page" style={{ background: themeWash(theme) }}>
      <div className="category-content">
        <CategoryHero label={category.label} theme={theme} period={period} weekControl={weekControl} />

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
                  isMovie={category.id === 'movies'}
                  onClick={() => {
                    const params = new URLSearchParams();
                    if (data?.weekStart) params.set('fromWeek', data.weekStart);
                    const query = params.toString();
                    navigate(`/trend/${item.key}${query ? `?${query}` : ''}`);
                  }}
                />
              ))}
            </DataState>
          </div>
        </div>
        <FAQ />
      </div>
    </div>
  );
}

export default function CategoryPage() 
{
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
