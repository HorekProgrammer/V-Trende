import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Cover from '../../src/components/common/Cover';

describe('Cover (Обложка)', () => {
  it('должен выводить инициалы, если нет обложки', () => {
    render(<Cover item={{ key: '1', title: 'Тест Трек', cover: null }} />);
    expect(screen.getByText('ТТ')).toBeInTheDocument();
  });

  it('должен рендерить картинку', () => {
    const { container } = render(<Cover item={{ key: '1', title: 'Тест', cover: 'https://example.com/img.jpg' }} />);
    const img = container.querySelector('img');
    expect(img).toHaveAttribute('src', 'https://example.com/img.jpg');
  });

  it('должен скрывать картинку при ошибке загрузки', () => {
    const { container } = render(<Cover item={{ key: '1', title: 'Тест', cover: 'https://broken.jpg' }} />);
    const img = container.querySelector('img');
    fireEvent.error(img);
    expect(container.querySelector('img')).toBeNull();
  });
});