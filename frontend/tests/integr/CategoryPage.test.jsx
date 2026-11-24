import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import CategoryPage from '../../src/pages/CategoryPage';

global.fetch = vi.fn();

describe('Интеграционный тест: Страница категории и фильтрация', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const setupFetchMock = (items = []) => {
    global.fetch.mockImplementation((url) => {
      if (url.includes('/weeks')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      }
      if (url.includes('/trends')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ weekStart: '2026-11-16', items }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
  };

  it('должен запрашивать данные с сортировкой по новизне при клике на фильтр', async () => {
    setupFetchMock([{ key: '1', title: 'Тестовая игра', genre: 'Экшен' }]);

    render(
      <MemoryRouter initialEntries={['/category/games']}>
        <Routes>
          <Route path="/category/:name" element={<CategoryPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Тестовая игра');
    await userEvent.click(screen.getByText('По новизне'));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('sort=new'),
        expect.anything()
      );
    });
  });

  it('должен фильтровать карточки при выборе жанра', async () => {
    setupFetchMock([
      { key: '1', title: 'Игра Экшен', genre: 'Экшен' },
      { key: '2', title: 'Игра Стратегия', genre: 'Стратегия' },
    ]);

    render(
      <MemoryRouter initialEntries={['/category/games']}>
        <Routes>
          <Route path="/category/:name" element={<CategoryPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText('Игра Экшен')).toBeInTheDocument();
    expect(screen.getByText('Игра Стратегия')).toBeInTheDocument();

    await userEvent.click(screen.getByText('Экшен'));

    expect(screen.queryByText('Игра Стратегия')).not.toBeInTheDocument();
    expect(screen.getByText('Игра Экшен')).toBeInTheDocument();
  });

  it('должен показывать заглушку, если нет данных', async () => {
    setupFetchMock([]); 

    render(
      <MemoryRouter initialEntries={['/category/games']}>
        <Routes>
          <Route path="/category/:name" element={<CategoryPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText('В этой категории пока нет данных')).toBeInTheDocument();
  });
});