import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import DetailPage from '../../src/pages/DetailPage'; 

global.fetch = vi.fn();

describe('Интеграционный тест: Страница детального просмотра тренда', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('должен загружать данные тренда по ID и отображать заголовок', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        key: '123',
        title: 'Тестовый Тренд',
        subtitle: 'Описание тренда',
        sphere: 'music', 
        rank: 1,
        history: [{ weekStart: '2026-11-16', rank: 1 }]
      }),
    });

    render(
      <MemoryRouter initialEntries={['/trend/123']}>
        <Routes>
          <Route path="/trend/:id" element={<DetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    const trendTitle = await screen.findByText('Тестовый Тренд');
    expect(trendTitle).toBeInTheDocument();

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/trends/123'), 
      expect.anything()
    );
  });

  it('должен показывать ошибку, если тренд не найден', async () => {
    global.fetch.mockResolvedValue({
      ok: false,
      status: 404,
    });

    render(
      <MemoryRouter initialEntries={['/trend/999']}>
        <Routes>
          <Route path="/trend/:id" element={<DetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    const errorMessage = await screen.findByText('Тренд не найден'); 
    expect(errorMessage).toBeInTheDocument();
  });
});