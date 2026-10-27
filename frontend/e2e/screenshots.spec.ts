import { test, expect } from '@playwright/test';

// Captures README / portfolio screenshots. Runs only when SCREENSHOTS=1.
test.skip(!process.env.SCREENSHOTS, 'Set SCREENSHOTS=1 to capture portfolio screenshots');

const pages = [
  ['01-executive-overview', 'overview', 'Revenue performance'],
  ['02-six-week-forecast', 'forecast', 'Daily revenue forecast'],
  ['03-store-analytics', 'stores', 'Explore your stores'],
  ['04-model-comparison', 'models', 'Predictions vs. reality'],
  ['05-explainable-ai', 'explain', 'What drives the model?'],
  ['06-data-quality', 'quality', 'Missing values & treatment'],
] as const;

test.use({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });

for (const [file, hash, marker] of pages) {
  test(`screenshot ${file}`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto(`/#${hash}`);
    await expect(page.getByText(marker, { exact: true }).first()).toBeVisible();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1200);
    await expect(page.getByRole('alert')).toHaveCount(0);
    await page.screenshot({ path: `../docs/screenshots/${file}.png` });
    await page.screenshot({ path: `../docs/screenshots/full/${file}.png`, fullPage: true });
    expect(errors).toEqual([]);
  });
}

test('screenshot mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/#overview');
  await expect(page.getByText('Revenue performance', { exact: true })).toBeVisible();
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1200);
  await page.screenshot({ path: '../docs/screenshots/07-mobile.png' });
});
