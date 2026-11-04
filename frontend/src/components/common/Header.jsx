import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import './Header.css';

const CATEGORIES = [
    {id: 'music', label: 'Музыка'},
    {id: 'movies', label: 'Фильмы'},
    {id: 'games', label: 'Игры'},
    {id: 'streamers', label: 'Стримеры'},
];

export default function Header() 
{
    const  {pathname} = useLocation();
    const activeCategory = pathname.startsWith('/category/') ? pathname.split('/')[2] : null;

    const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');

    useEffect(() => {
        document.documentElement.dataset.theme = theme;
        localStorage.setItem('theme', theme);
    }, [theme]);

    const toggleTheme = () => {
        const next = theme === 'dark' ? 'light' : 'dark';

        if (!document.startViewTransition) {
            setTheme(next);
            return;
        }

        document.startViewTransition(() => {
            document.documentElement.dataset.theme = next;
            setTheme(next);
        });
    };

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
                <button
                    type="button"
                    className='theme-toggle'
                    onClick={toggleTheme}
                    aria-label="Сменить тему"
                >
                    {theme === 'dark' ? '\u2600\uFE0E' : '\u263E'}
                </button>
                <Link to="/auth" className='btn-primary'>Регистрация</Link>
            </div>
        </header>
    );
}