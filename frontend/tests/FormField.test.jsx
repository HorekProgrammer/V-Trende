import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import FormField from '../src/components/auth/FormField';

describe('FormField (Поле ввода)', () => {
  it('должен рендерить лейбл и инпут', () => {
    render(<FormField id="test" label="Email" placeholder="Введите email" />);
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Введите email')).toBeInTheDocument();
  });
  it('не должен показывать ошибку по умолчанию', () => {
    render(<FormField id="test" label="Email" />);
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'false');
  });
  it('должен выводить текст ошибки', () => {
    render(<FormField id="test" label="Email" error="Ошибка" />);
    expect(screen.getByText('Ошибка')).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true');
  });
});