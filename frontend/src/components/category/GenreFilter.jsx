export default function GenreFilter({ genres, selected, onToggle }) 
{
  return (
    <div>
      {genres.map((g) => (
        <label key={g} className="checkbox-row">
          <input
            type="checkbox"
            checked={selected.includes(g)}
            onChange={() => onToggle(g)}
          />
          {g}
        </label>
      ))}
    </div>
  );
}