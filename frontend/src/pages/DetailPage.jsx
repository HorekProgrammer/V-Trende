import { useEffect } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { useWeek } from '../api/useWeek';
import DetailHero from '../components/detail/DetailHero';
import StatGrid from '../components/detail/StatGrid';
import PopularityCard from '../components/detail/PopularityCard';
import DataState from '../components/common/DataState';
import WeekSwitcher from '../components/common/WeekSwitcher';
import { CATEGORIES } from '../components/category/categories';
import { useApi } from '../api/useApi';
import { trendPath } from '../api/paths';
import './DetailPage.css';

function BackIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M15 6l-6 6 6 6"
        stroke="currentColor"
        strokeWidth="2.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function DetailPage() {
  const location = useLocation();
  const { id } = useParams();
  const [week, setWeek] = useWeek();
  const fromWeek = new URLSearchParams(location.search).get('fromWeek');
  const backWeekQuery = fromWeek ? `?week=${encodeURIComponent(fromWeek)}` : '';
  const { data: item, loading, error } = useApi(trendPath(id, week));
  const category = item ? CATEGORIES.find((c) => c.id === item.sphere) : null;
  const availableWeeks = item?.history
    ?.filter((point) => point.rank != null)
    .map((point) => point.weekStart)
    .reverse() || [];

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [id]);

  useEffect(() => {
    if (item) {
      document.title = item.subtitle
        ? `${item.title} — ${item.subtitle} — популярность и история | В ЧАРТЕ`
        : `${item.title} — популярность, место в рейтинге и история | В ЧАРТЕ`;
    }
  }, [item]);

  const notFound = error && (error.status === 404 || error.status === 422);
  if (notFound) 
  {
    return (
      <div className="detail-wrap">
        <p>Тренд не найден</p>
        <Link to="/" className="back-btn">
          <BackIcon />
          На главную
        </Link>
      </div>
    );
  }

  return (
    <div className="detail-wrap">
      <Link
        to={location.state?.from || (category ? `/category/${category.id}${backWeekQuery}` : '/')}
        state={location.state?.scrollY != null ? { restoreScrollY: location.state.scrollY } : null}
        className="back-btn"
      >
        <BackIcon />
        {location.state?.from ? 'Назад' : category ? 'Назад к чарту' : 'На главную'}
      </Link>

      <DataState loading={loading} error={error}>
        {item && category && (
          <>
            <div className="detail-week-switcher">
              <WeekSwitcher weeks={availableWeeks} value={week} onChange={setWeek} />
            </div>
            <DetailHero item={item} category={category} />
            <StatGrid item={item} />

            {item.history.some((point) => point.rank != null) && (
              <PopularityCard key={item.key} history={item.history} topSize={category.topSize} />
            )}
          </>
        )}
      </DataState>
    </div>
  );
}
