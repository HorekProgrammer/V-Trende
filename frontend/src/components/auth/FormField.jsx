import './FormField.css';

export default function FormField({ id, label, error, ...inputProps }) 
{
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input id={id} aria-invalid={Boolean(error)} {...inputProps} />
      {error && <div className="field-error">{error}</div>}
    </div>
  );
}