import './Top3Block.css';

const COVER_GRADIENTS =
[
  'linear-gradient(135deg, #FF7A29, #D62828)',
  'linear-gradient(135deg, #29E1B5, #2B6CF6)',
  'linear-gradient(135deg, #F2B84B, #D62828)',
  'linear-gradient(135deg, #2B6CF6, #FF7A29)',
  'linear-gradient(135deg, #D62828, #F2B84B)',
  'linear-gradient(135deg, #29E1B5, #FF7A29)',
];

function coverGrad(seedStr) 
{
  let h = 0;
  for (const c of seedStr) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return COVER_GRADIENTS[h % COVER_GRADIENTS.length];
}

function initials(str) 
{
  return str.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase();
}

export default function Top3Block({id, title, description, groups, onItemClick }) 
{
  return (
    <div className="group-block" id={id}>
      <div className="group-head">
        <h2>{title}</h2>
      </div>
      {description && <p className="group-desc">{description}</p>}

      <div className="top3-columns">
        {groups.map(({ category, items }) => (
          <div className="top3-col" key={category.id}>
            <div className="top3-col-head">{category.label}</div>
            {items.map((item) => (
              <div
                className="top3-item"
                key={item.key}
                onClick={() => onItemClick?.(item)}
              >
                <div className="top3-rank">{item.rank}</div>
                <div className="top3-cover" style={{ background: coverGrad(item.key) }}>
                  {initials(item.title)}
                </div>
                <div className="top3-info">
                  <div className="top3-title">{item.title}</div>
                  <div className="top3-sub">{item.subtitle}</div>
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}