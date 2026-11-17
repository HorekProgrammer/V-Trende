import { test, expect } from '@playwright/test';

test.describe('Сквозные сценарии (E2E)', () => {
  
  test('Сценарий 1: Загрузка главной страницы', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('h2', { hasText: 'Глобальное' })).toBeVisible({ timeout: 10000 });
    const firstCard = page.locator('.mini-card').first();
    await expect(firstCard).toBeVisible();
  });

  test('Сценарий 2: Переход в категорию "Игры" и фильтрация', async ({ page }) => {
    await page.goto('/');
    await page.locator('.nav-item', { hasText: 'Игры' }).click();
    await expect(page.locator('.cat-title')).toHaveText('Игры', { timeout: 10000 });
    await page.locator('.sort-chip', { hasText: 'По новизне' }).click();
    await expect(page.locator('.sort-chip', { hasText: 'По новизне' })).toHaveClass(/is-active/);
  });

});