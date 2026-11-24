import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MiniCard from '../../src/components/trends/MiniCard';

describe('MiniCard (Мини-карточка)', () => {
  it('должен рендерить данные', () => {
    render(<MiniCard item={{ key: '1', title: 'Заголовок', subtitle: 'Подзаголовок', categoryLabel: 'Музыка' }} />);
    expect(screen.getByText('Заголовок')).toBeInTheDocument();
    expect(screen.getByText('Подзаголовок')).toBeInTheDocument();
  });
  
  it('должен вызывать onClick при клике', () => {
    let clicked = false;
    render(<MiniCard item={{ key: '1', title: 'Тест' }} onClick={() => { clicked = true; }} />);
    screen.getByText('Тест').click();
    expect(clicked).toBe(true);
  });
});