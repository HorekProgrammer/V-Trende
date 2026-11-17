import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import CategoryPage from '../src/pages/CategoryPage';

global.fetch = vi.fn();

describe('Интеграционный тест: Страница категории и фильтрация', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('должен запрашивать данные с сортировкой по новизне при клике на фильтр', async () => {
    global.fetch.mockImplementation((url) => {
      if (url.includes('/weeks')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      }
      
      if (url.includes('/trends')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ 
            weekStart: '2026-11-16',
            items: [{ key: '1', title: 'Тестовая игра', genre: 'Экшен' }] 
          }),
        });
      }

      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(
      <MemoryRouter initialEntries={['/category/games']}>
        <Routes>
          <Route path="/category/:name" element={<CategoryPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Тестовая игра');

    const newSortBtn = screen.getByText('По новизне');
    await userEvent.click(newSortBtn);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('sort=new'),
        expect.anything()
      );
    });
  });
});