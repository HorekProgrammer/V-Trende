import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import TrendCard from '../src/components/trends/TrendCard';

const mockItem = { key: '1', rank: 2, prevRank: 4, peak: 1, weeks: 5, title: 'Тест', subtitle: 'Суб', isNew: false };

describe('TrendCard (Карточка тренда)', () => {
  it('должен показывать стрелку вверх', () => {
    render(<TrendCard item={mockItem} />);
    expect(screen.getByText('▲ 2')).toBeInTheDocument();
  });
  it('должен показывать стрелку вниз', () => {
    render(<TrendCard item={{ ...mockItem, rank: 5, prevRank: 1 }} />);
    expect(screen.getByText('▼ 4')).toBeInTheDocument();
  });
  it('должен показывать NEW', () => {
    render(<TrendCard item={{ ...mockItem, isNew: true }} />);
    expect(screen.getByText('NEW')).toBeInTheDocument();
  });
  it('должен показывать прочерк, если не было рейтинга', () => {
    render(<TrendCard item={{ ...mockItem, prevRank: null, isNew: false }} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });
  it('должен добавлять класс медали для топ-3', () => {
    const { container } = render(<TrendCard item={{ ...mockItem, rank: 1 }} />);
    expect(container.firstChild).toHaveClass('rank-1');
  });
});