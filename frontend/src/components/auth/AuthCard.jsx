import { Link } from 'react-router-dom';
import './AuthCard.css';

export default function AuthCard({ title, subtitle, children }) 
{
  return (
    <div className="auth-card">
      <Link to="/" className="logo auth-logo">
        <div className="logo-word">
          В <span>ТРЕНДЕ</span>
        </div>
      </Link>
      <h1 className="auth-h">{title}</h1>
      <p className="auth-p">{subtitle}</p>
      {children}
    </div>
  );
}