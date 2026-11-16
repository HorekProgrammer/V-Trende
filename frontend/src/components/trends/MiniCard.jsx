import './MiniCard.css';
import Cover from '../common/Cover';


export default function MiniCard({ item, onClick }) {
  return (
    <a
      className="mini-card"
      href={`/trend/${item.key}`}
      onClick={(event) => {
        if (!onClick || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        onClick();
      }}
    >
      <Cover item={item} className="mini-cover" />
      <div className="mini-body">
        <div className="mini-tag">{item.categoryLabel || item.sphere}</div>
        <div className="mini-title">{item.title}</div>
        <div className="mini-sub">{item.subtitle}</div>
      </div>
    </a>
  );
}
