import { test, expect } from '@playwright/test';

test('all six dashboard pages load without browser errors', async ({ page }) => {
  const errors:string[]=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');
  await expect(page.getByText('Revenue performance',{exact:true})).toBeVisible();
  await expect(page.getByText('Total revenue',{exact:true})).toBeVisible();
  await page.screenshot({path:'test-results/dashboard-desktop.png',fullPage:true});
  const routes=[['6-Week Forecasting','Daily revenue forecast'],['Store Analytics','Explore your stores'],['Model Comparison','Predictions vs. reality'],['Explainable AI','What drives the model?'],['Data Quality','Missing values & treatment']];
  for(const [label,heading] of routes){
    await page.getByRole('navigation').getByRole('button',{name:label,exact:false}).click();
    await expect(page.getByRole('heading',{name:heading,exact:true})).toBeVisible();
    await expect(page.getByRole('alert')).toHaveCount(0);
  }
  expect(errors).toEqual([]);
});

test('forecast filters, cumulative view and CSV export work',async({page})=>{
  await page.goto('/#forecast');
  await expect(page.getByRole('heading',{name:'Daily revenue forecast'})).toBeVisible();
  await page.getByLabel('Select store').selectOption('1');
  await page.getByLabel('Forecast model').selectOption('Ridge');
  await page.getByLabel('Forecast horizon',{exact:true}).selectOption('14');
  await expect(page.getByText('14 days',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Cumulative',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Cumulative revenue forecast'})).toBeVisible();
  const downloadPromise=page.waitForEvent('download');
  await page.getByRole('link',{name:'Export forecast'}).click();
  const download=await downloadPromise;
  expect(download.suggestedFilename()).toBe('salevora-ridge-14d.csv');
  await page.screenshot({path:'test-results/forecast-desktop.png',fullPage:true});
});

test('history filter and store search apply to real data',async({page})=>{
  await page.goto('/');
  await expect(page.getByText('Revenue performance',{exact:true})).toBeVisible();
  await page.getByLabel('Select store').selectOption('1');
  await page.getByLabel('Historical period').selectOption('28');
  await expect(page.getByText('28-day view',{exact:true})).toBeVisible();
  await page.getByRole('navigation').getByRole('button',{name:'Store Analytics'}).click();
  await expect(page.getByRole('heading',{name:'Store 1 · revenue history'})).toBeVisible();
  await page.getByRole('button',{name:'Clear store filter'}).click();
  await page.getByLabel('Search store ID').fill('1115');
  await expect(page.getByRole('button',{name:'Store 1115',exact:true})).toBeVisible();
  await expect(page.locator('tbody tr')).toHaveCount(1);
  await page.getByLabel('Search store ID').fill('no-store');
  await expect(page.getByText('No stores match these filters.')).toBeVisible();
});

test('mobile navigation, layout and methodology dialog work',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  await expect(page.getByText('Revenue performance',{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/dashboard-mobile.png',fullPage:true});
  await page.getByRole('button',{name:'Open navigation',exact:true}).click();
  await page.getByRole('navigation').getByRole('button',{name:'Explainable AI'}).click();
  await expect(page.getByText('What drives the model?',{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.getByRole('button',{name:'Project information'}).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
});
