import './MiniCard.css';
import Cover from '../common/Cover';


export default function MiniCard({ item, onClick }) {
  return (
    <div className="mini-card" onClick={onClick}>
      <Cover item={item} className="mini-cover" />
      <div className="mini-body">
        <div className="mini-tag">{item.categoryLabel || item.sphere}</div>
        <div className="mini-title">{item.title}</div>
        <div className="mini-sub">{item.subtitle}</div>
      </div>
    </div>
  );
}
