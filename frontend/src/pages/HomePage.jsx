import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import GroupBlock from '../components/trends/GroupBlock';
import Top3Block from '../components/trends/Top3Block';
import CrownIcon from '../components/icons/CrownIcon';
import HomeSidebar from '../components/common/HomeSidebar';
import { getGlobalTrends, getNewTrends, getLegendaryTrends, getTop3ByCategory} from '../mocks/mockData';
import './HomePage.css';

const SECTIONS = 
[
  { id: 'group-global', label: 'Глобальное' },
  { id: 'group-new', label: 'Новые релизы' },
  { id: 'group-legendary', label: 'Легендарное' },
  { id: 'group-top3', label: 'Топ-3' },
];

export default function HomePage() {
  const navigate = useNavigate();
  const [activeId, setActiveId] = useState(SECTIONS[0].id);
  const openTrend = (item) => navigate(`/trend/${item.key}`);
  
  return (
    <div className="home-layout">
      <HomeSidebar sections={SECTIONS} activeId={activeId} onSelect={setActiveId} />

      <main className="home">
        <section className="hero">
          <h1>Всё, что сейчас обсуждают — в одной ленте</h1>
        </section>

        <GroupBlock
          id="group-global"
          title="Глобальное"
          description="Самое популярное прямо сейчас во всех категориях — музыка, фильмы, игры и стримеры вместе."
          items={getGlobalTrends(10)}
          onItemClick={openTrend}
        />

        <GroupBlock
          id="group-new"
          title="Новые релизы"
          description="Только появились в чартах — меньше всего недель в топе."
          items={getNewTrends(8)}
          onItemClick={openTrend}
          variant="grid"
        />

        <GroupBlock
          id="group-legendary"
          title="Легендарное"
          description="Держится в чартах дольше всех — проверено временем."
          items={getLegendaryTrends(8)}
          onItemClick={openTrend}
          variant="legend"
          icon={<CrownIcon />}
        />

        <Top3Block
          id="group-top3"
          title="Топ-3"
          description="Тройка лидеров в каждой из категорий."
          groups={getTop3ByCategory()}
          onItemClick={openTrend}
        />

      </main>
    </div>
  );
}