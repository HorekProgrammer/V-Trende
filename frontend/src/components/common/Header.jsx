import { Link } from 'react-router-dom';
import './Header.css';

const CATEGORIES = [
    {id: 'music', label: 'Музыка'},
    {id: 'movies', label: 'Фильмы'},
    {id: 'games', label: 'Игры'},
    {id: 'streamers', label: 'Стримеры'},
];

export default function Header ({ activeCategory }) {
    return (
        <header className='topbar'>
            <Link to="/" className='logo'>
                <div className='logo-word'>В <span>ТРЕНДЕ</span></div>
            </Link>

            <nav className='nav-spheres'>
                {CATEGORIES.map((cat) => (
                    <Link key={cat.id} to={`/category/${cat.id}`} 
                        className={`nav-item ${activeCategory === cat.id ? 'is-active' : ''}`} > 
                        {cat.label}
                    </Link>
                ))}
            </nav>

            <div className='nav-right'>
                <Link to="/auth" className='btn-primary'>Регистрация</Link>
            </div>
        </header>
    );
}