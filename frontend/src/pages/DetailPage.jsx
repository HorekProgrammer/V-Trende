import { useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import DetailHero from '../components/detail/DetailHero';
import StatGrid from '../components/detail/StatGrid';
import PopularityCard from '../components/detail/PopularityCard';
import DataState from '../components/common/DataState';
import { CATEGORIES } from '../components/category/categories';
import { useApi } from '../api/useApi';
import { trendPath } from '../api/paths';
import './DetailPage.css';

function BackIcon() 
{
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

export default function DetailPage() 
{
  const { id } = useParams();
  const { data: item, loading, error } = useApi(trendPath(id));
  const category = item ? CATEGORIES.find((c) => c.id === item.sphere) : null;

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [id]);

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
      <Link to={category ? `/category/${category.id}` : '/'} className="back-btn">
        <BackIcon />
        {category ? 'Назад к чарту' : 'На главную'}
      </Link>

      <DataState loading={loading} error={error}>
        {item && category && (
          <>
            <DetailHero item={item} category={category} />
            <StatGrid item={item} />
            <PopularityCard key={item.key} history={item.history} topSize={category.topSize} />
          </>
        )}
      </DataState>
    </div>
  );
}