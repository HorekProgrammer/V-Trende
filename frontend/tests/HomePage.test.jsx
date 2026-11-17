import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import HomePage from '../src/pages/HomePage';

global.fetch = vi.fn();

describe('Интеграционный тест: Лента на главной странице', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('должен показывать загрузку, а затем карточки трендов', async () => {
    const mockFeedData = {
      global: [{ key: '1', title: 'Тестовый тренд 1', subtitle: 'Музыка', rank: 1 }],
      new: [], legendary: [], top3: []
    };

    global.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockFeedData),
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    );

    expect(screen.getByText('Загрузка…')).toBeInTheDocument();

    const trendTitles = await screen.findAllByText('Тестовый тренд 1');
    expect(trendTitles.length).toBeGreaterThan(0);
  });
});