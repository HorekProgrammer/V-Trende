import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import GroupBlock from '../components/trends/GroupBlock';
import Top3Block from '../components/trends/Top3Block';
import CrownIcon from '../components/icons/CrownIcon';
import HomeSidebar from '../components/common/HomeSidebar';
import DataState from '../components/common/DataState';
import { useApi } from '../api/useApi';
import { feedPath } from '../api/paths';
import './HomePage.css';

const SECTIONS = 
[
  { id: 'group-global', label: 'Глобальное' },
  { id: 'group-new', label: 'Новые релизы' },
  { id: 'group-legendary', label: 'Легендарное' },
  { id: 'group-top3', label: 'Топ-3' },
];

export default function HomePage() 
{
  const navigate = useNavigate();
  const [activeId, setActiveId] = useState(SECTIONS[0].id);
  const { data, loading, error } = useApi(feedPath());
  const openTrend = (item) => navigate(`/trend/${item.key}`);

  return (
    <div className="home-layout">
      <HomeSidebar sections={SECTIONS} activeId={activeId} onSelect={setActiveId} />

      <main className="home">
        <section className="hero">
          <h1>Всё, что сейчас обсуждают — в одной ленте</h1>
        </section>

        <DataState loading={loading} error={error}>
          {data && (
            <>
              {data.global.length > 0 && (
                <GroupBlock
                  id="group-global"
                  title="Глобальное"
                  description="Самое популярное прямо сейчас во всех категориях — музыка, фильмы, игры и стримеры вместе."
                  items={data.global}
                  onItemClick={openTrend}
                />
              )}

              {data.new.length > 0 && (
                <GroupBlock
                  id="group-new"
                  title="Новые релизы"
                  description="Только появились в чартах — меньше всего недель в топе."
                  items={data.new}
                  onItemClick={openTrend}
                  variant="grid"
                />
              )}

              {data.legendary.length > 0 && (
                <GroupBlock
                  id="group-legendary"
                  title="Легендарное"
                  description="Держится в чартах дольше всех — проверено временем."
                  items={data.legendary}
                  onItemClick={openTrend}
                  variant="legend"
                  icon={<CrownIcon />}
                />
              )}

              <Top3Block
                id="group-top3"
                title="Топ-3"
                description="Тройка лидеров в каждой из категорий."
                groups={data.top3}
                onItemClick={openTrend}
              />
            </>
          )}
        </DataState>
      </main>
    </div>
  );
}