/* Browser smoke test for the locally vendored xterm.js terminal. */
const { chromium } = require("playwright");

const baseUrl = process.argv[2] || "http://127.0.0.1:8176";

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.OBUS_BROWSER_EXE || undefined,
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  const frames = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("websocket", (socket) => socket.on("framereceived", (frame) => frames.push(String(frame.payload || ""))));
  try {
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    await page.waitForFunction(() => typeof window.Terminal === "function" && !!window.FitAddon?.FitAddon);
    await page.evaluate(() => document.querySelectorAll("dialog[open]").forEach((dialog) => dialog.close()));
    await page.evaluate(() => document.querySelector('[data-terminal-view="shell"]')?.click());
    await page.waitForSelector("#shell-output .xterm");
    await page.waitForFunction(() => document.querySelector("#shell-state")?.textContent === "Ready");
    await page.locator("#shell-output .xterm textarea").click();
    await page.keyboard.type("Write-Output 'OBUS_XTERM_UI_READY'");
    await page.keyboard.press("Enter");
    for (let attempt = 0; attempt < 150 && !frames.some((frame) => frame.includes("OBUS_XTERM_UI_READY")); attempt += 1) {
      await page.waitForTimeout(100);
    }
    if (!frames.some((frame) => frame.includes("OBUS_XTERM_UI_READY"))) {
      throw new Error(`terminal WebSocket did not return marker; frames=${frames.slice(-8).join(" | ")}`);
    }
    const state = await page.locator("#shell-state").innerText();
    const xterm = await page.locator("#shell-output .xterm").count();
    const overview = await page.locator("#runtime-parallel-limit").innerText();
    if (errors.length) throw new Error(errors.join("\n"));
    console.log(JSON.stringify({ state, xterm, parallelLimit: overview, result: "OBUS_XTERM_UI_READY" }));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
