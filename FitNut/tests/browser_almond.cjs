// Desktop/mobile UI verification. Writer responses are explicitly mocked, never billed.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
(async () => {
  const baseURL = process.env.FITNUT_URL || 'http://127.0.0.1:5000';
  if (!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(baseURL)) throw new Error('Use a local test app.');
  const browser = await chromium.launch({headless: true, ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? {executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE} : {})});
  const context = await browser.newContext({baseURL, viewport: {width: 1100, height: 900}});
  const page = await context.newPage();
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  const output = path.resolve('.test-results'); await fs.mkdir(output, {recursive: true});
  const email = `almond-browser-${Date.now()}@example.test`, password = 'Local-browser-only-42';
  try {
    assert.equal((await context.request.post('/register', {data: {first_name: 'Almond Test', last_name: 'User', email, password, password_confirmation: password}})).status(), 201);
    await page.goto('/login'); await page.getByLabel('Email').fill(email); await page.getByLabel('Password', {exact: true}).fill(password);
    await page.getByRole('button', {name: 'Log in', exact: true}).click(); await page.waitForURL('**/dashboard');
    await page.getByText('Not available yet', {exact: true}).waitFor();
    assert.equal(await page.locator('#almond-suggestions button').count(), 4);
    assert.equal(await page.locator('#almond-send').isDisabled(), true);
    await page.locator('#almond-gate').waitFor();
    assert.equal(await page.locator('#almond-workspace').evaluate(node => node.inert), true);
    await page.getByRole('button', {name: 'No allergies', exact: true}).click();
    await page.locator('#almond-gate').waitFor({state: 'hidden'});
    assert.equal((await (await context.request.get('/profile-data')).json()).profile.allergy_status, 'none_reported');
    await page.locator('#almond details').filter({has: page.getByText('Personal preferences', {exact: true})}).locator('summary').click();
    await page.getByLabel('Preferred cuisines, one per line').fill('Cajun\nMediterranean');
    await page.getByLabel('Cooking time (minutes)', {exact: true}).fill('20');
    await page.getByRole('button', {name: 'Confirm and save preferences', exact: true}).click();
    await page.getByText('Almond preferences saved.', {exact: true}).waitFor();
    await page.reload(); await page.getByText('Not available yet', {exact: true}).waitFor();
    assert.equal(await page.locator('#almond-memory [name=cuisines]').inputValue(), 'Cajun\nMediterranean');
    for (const url of ['/food', '/activity']) { await page.goto(url); await page.getByRole('heading', {name: 'Ask Almond', exact: true}).waitFor(); }
    for (const url of ['/profile', '/sleep']) { await page.goto(url); assert.equal(await page.locator('#almond').count(), 0); }
    await page.goto('/dashboard'); await page.getByText('Not available yet', {exact: true}).waitFor();
    await page.screenshot({path: path.join(output, 'almond-desktop.png'), fullPage: true});
    await page.setViewportSize({width: 390, height: 844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({path: path.join(output, 'almond-mobile.png'), fullPage: true});
    // Exercise the successful chat/render/log-draft path without an API credential or real writer.
    await page.route('**/almond/state', async route => { const response = await route.fetch(); const state = await response.json(); state.enabled = true; await route.fulfill({json: state}); });
    const food = {food_id: 987654321, food_name: 'UI test apple', grams: 150, source_url: 'https://fdc.nal.usda.gov/'};
    const recipe = {title: '<script>UI recipe</script>', foods: [food], instructions: ['Slice the apple.'], substitutions: [], nutrition: {calories: 78, protein_g: .3, carbs_g: 21, fat_g: .2}, note: 'UI mock only.'};
    await page.route('**/almond/messages', async route => { const request = route.request(); assert.ok(request.headers()['x-csrf-token']); const body = request.postDataJSON(); assert.ok(body.request_id); assert.equal(body.text, 'A test meal'); await route.fulfill({json: {reply: '<img src=x onerror=alert(1)>', recipe, recipe_id: 987654321}}); });
    await page.reload(); await page.getByText('Ready', {exact: true}).waitFor();
    await page.locator('#almond-question').fill('A test meal'); await page.locator('#almond-question').press('Enter');
    await page.getByRole('heading', {name: recipe.title, exact: true}).waitFor();
    assert.equal(await page.locator('#almond-messages img, #almond-recipes script').count(), 0);
    await page.route('**/almond/recipes/987654321/draft', route => route.fulfill({json: {recipe, foods: [{food_id: food.food_id, food_name: food.food_name, quantity: 150, quantity_unit: 'g'}], saved: false}}));
    await page.route('**/food-preview', route => route.fulfill({json: {item: {food_name: food.food_name, quantity: 150, quantity_unit: 'g', calories: 78, protein_g: .3, carbs_g: 21, fat_g: .2, fiber_g: 3}}}));
    await page.getByRole('button', {name: 'See recipe', exact: true}).click();
    await page.getByRole('button', {name: 'Log this meal', exact: true}).click(); await page.waitForURL('**/food');
    await page.getByText('Almond meal draft loaded. Review the foods and portions before saving.', {exact: true}).waitFor();
    assert.equal(await page.locator('#draft-items li').count(), 1);
    assert.equal(await page.locator('#save-meal').isVisible(), true);
    assert.deepEqual(errors, []);
    console.log('Almond desktop/mobile, placement, preference persistence, XSS escaping, chat and unsaved draft checks passed (mocked inference).');
  } finally { await page.unrouteAll({behavior: 'wait'}); await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
