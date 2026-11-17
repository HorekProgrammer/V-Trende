import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Cover from '../src/components/common/Cover';

describe('Cover (Обложка)', () => {
  it('должен выводить инициалы, если нет обложки', () => {
    render(<Cover item={{ key: '1', title: 'Тест Трек', cover: null }} />);
    expect(screen.getByText('ТТ')).toBeInTheDocument();
  });
  it('должен рендерить картинку', () => {
    render(<Cover item={{ key: '1', title: 'Тест', cover: 'https://example.com/img.jpg' }} />);
    expect(screen.getByRole('img', { hidden: true })).toHaveAttribute('src', 'https://example.com/img.jpg');
  });
  it('должен скрывать картинку при ошибке загрузки', () => {
    render(<Cover item={{ key: '1', title: 'Тест', cover: 'https://broken.jpg' }} />);
    const img = screen.getByRole('img', { hidden: true });
    fireEvent.error(img);
    expect(screen.queryByRole('img', { hidden: true })).not.toBeInTheDocument();
  });
});