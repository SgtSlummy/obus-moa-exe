const { chromium } = require('../.smoke-electron/node_modules/playwright-core');

(async () => {
  const browser = await chromium.connectOverCDP('http://127.0.0.1:9229');
  const contexts = browser.contexts();
  const page = contexts.flatMap((context) => context.pages())[0];
  if (!page) throw new Error('Packaged Electron window did not expose a page');
  await page.waitForSelector('.side', { state: 'visible', timeout: 15000 });
  const initial = await page.evaluate(() => ({
    url: location.href,
    collapsed: document.body.dataset.sidebarCollapsed,
    sidebarDisplay: getComputedStyle(document.querySelector('.side')).display,
    sidebarWidth: Math.round(document.querySelector('.side').getBoundingClientRect().width),
    activePage: document.querySelector('.page.active')?.dataset.pagePanel,
  }));
  if (initial.url !== 'http://127.0.0.1:38173/') throw new Error(`Unexpected URL: ${initial.url}`);
  if (initial.sidebarDisplay === 'none' || initial.sidebarWidth < 70) throw new Error(`Sidebar hidden: ${JSON.stringify(initial)}`);
  if (initial.activePage !== 'dashboard') throw new Error(`Dashboard not active: ${JSON.stringify(initial)}`);

  for (const target of ['plan', 'settings', 'dashboard']) {
    await page.locator(`#workspace-nav button[data-page="${target}"]`).click();
    await page.waitForFunction((name) => document.querySelector('.page.active')?.dataset.pagePanel === name, target);
    const visible = await page.locator('.side').isVisible();
    if (!visible) throw new Error(`Sidebar disappeared after switching to ${target}`);
  }

  await page.locator('#sidebar-toggle').click();
  await page.waitForFunction(() => document.body.dataset.sidebarCollapsed === 'true');
  const collapsedWidth = await page.locator('.side').evaluate((element) => Math.round(element.getBoundingClientRect().width));
  if (collapsedWidth < 70) throw new Error(`Collapsed sidebar vanished (${collapsedWidth}px)`);
  await page.locator('#sidebar-toggle').click();
  await page.waitForFunction(() => document.body.dataset.sidebarCollapsed === 'false');
  const restoredWidth = await page.locator('.side').evaluate((element) => Math.round(element.getBoundingClientRect().width));
  if (restoredWidth < 200) throw new Error(`Expanded sidebar did not restore (${restoredWidth}px)`);

  console.log(JSON.stringify({ ok: true, initial, collapsedWidth, restoredWidth }));
  await browser.close();
})().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
