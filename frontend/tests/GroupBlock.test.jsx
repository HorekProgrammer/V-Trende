import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import GroupBlock from '../src/components/trends/GroupBlock';

const mockItems = [
  { key: '1', title: 'Тренд 1', weeks: 5, categoryLabel: 'Музыка' },
  { key: '2', title: 'Тренд 2', weeks: 10, categoryLabel: 'Игры' },
];

describe('GroupBlock (Блок группы)', () => {
  it('должен рендерить сетку', () => {
    render(<GroupBlock id="test" title="Сетка" items={mockItems} variant="grid" />);
    expect(screen.getByText('Тренд 1')).toBeInTheDocument();
    expect(screen.getByText('Тренд 2')).toBeInTheDocument();
  });
  it('должен рендерить карусель по умолчанию (3 копии)', () => {
    render(<GroupBlock id="group-global" title="Карусель" items={mockItems} />);
    expect(screen.getAllByText('Тренд 1').length).toBe(3);
  });
});