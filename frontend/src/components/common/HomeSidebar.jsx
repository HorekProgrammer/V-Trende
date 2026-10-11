import './HomeSidebar.css';

export default function HomeSidebar({ sections, activeId, onSelect }) 
{
  return (
    <aside className="home-sidebar">
      <div className="side-title">РАЗДЕЛЫ ЛЕНТЫ</div>
      {sections.map((section) => (
        <a
          key={section.id}
          href={`#${section.id}`}
          className={`side-link ${activeId === section.id ? 'is-active' : ''}`}
          onClick={() => onSelect(section.id)}
        >
          <span className="dot" />
          {section.label}
        </a>
      ))}
    </aside>
  );
}