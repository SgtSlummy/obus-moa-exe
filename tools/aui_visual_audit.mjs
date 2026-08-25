import {mkdir, writeFile} from "node:fs/promises";
import path from "node:path";
import {pathToFileURL} from "node:url";

export const GOLDEN_RATIO = 1.61803398875;

export const SCORE_WEIGHTS = Object.freeze({
  geometry: 20,
  typography: 12,
  goldenRatio: 10,
  spacing: 10,
  responsive: 12,
  accessibility: 12,
  adjustability: 10,
  identity: 8,
  polish: 3,
  stability: 3,
});

const DEFAULT_PAGES = Object.freeze([
  "run",
  "cards-keys",
  "agents",
  "runtime",
  "rooms",
  "receipts",
  "visual-studio",
  "routing",
  "memory",
  "setup",
]);

const PAGE_IDS = Object.freeze({
  run: "dashboard",
  "cards-keys": "providers",
  agents: "agents",
  runtime: "runtime",
  rooms: "rooms",
  receipts: "runs",
  "visual-studio": "studios",
  routing: "decks",
  memory: "memory",
  setup: "settings",
});

export function overlapArea(a, b, {nested = false} = {}) {
  if (nested) return 0;
  const width = Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x));
  const height = Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
  return width * height;
}

export function isRectInViewport(rect, viewportWidth, viewportHeight) {
  return rect.x + rect.width >= 0 && rect.y + rect.height >= 0 &&
    rect.x <= viewportWidth && rect.y <= viewportHeight;
}

export function layoutRatio(firstRect, secondRect) {
  if (!firstRect || !secondRect || Math.abs(firstRect.y - secondRect.y) > 2) return null;
  if (firstRect.width <= 0 || secondRect.width <= 0) return null;
  return Math.max(firstRect.width, secondRect.width) / Math.min(firstRect.width, secondRect.width);
}

export function paneLayoutRatio(items) {
  const panes = (items || []).filter((item) => item.role !== "separator");
  if (panes.length < 2) return null;
  return layoutRatio(panes[0].rect, panes[panes.length - 1].rect);
}

export function deviceMetricsFor(width, height) {
  return {width, height, deviceScaleFactor: 1, mobile: false};
}

export function effectiveSettleMs(value) {
  return Math.max(800, Number(value) || 0);
}

export function imageGeometryIssue({complete, naturalWidth, naturalHeight, width, height}, tolerance = 0.03) {
  if (!complete || naturalWidth <= 0 || naturalHeight <= 0 || width <= 0 || height <= 0) return "broken";
  const naturalRatio = naturalWidth / naturalHeight;
  const renderedRatio = width / height;
  return Math.abs(Math.log(renderedRatio / naturalRatio)) > tolerance ? "distorted" : null;
}

export function isInvalidSeparator({orientation, minimum, now, maximum}) {
  if (!["horizontal", "vertical"].includes(orientation)) return true;
  return ![minimum, now, maximum].every(Number.isFinite) || minimum > now || now > maximum;
}

export function validatePreparationResult(result, expectedPageId, expectedDensity) {
  if (!result?.buttonFound) throw new Error(`Page button missing for ${expectedPageId}`);
  if (result.foreignVisibleRoots > 0) throw new Error(`Foreign visible browser overlay detected (${result.foreignVisibleRoots})`);
  if (!result.panelVisible || result.actualPageId !== expectedPageId || result.actualDensity !== expectedDensity) {
    throw new Error(`Audit state mismatch: expected ${expectedPageId}/${expectedDensity}, got ${result?.actualPageId}/${result?.actualDensity}`);
  }
  return result;
}

export function ratioScore(ratio) {
  if (!Number.isFinite(ratio) || ratio <= 0) return 0;
  const logarithmicDistance = Math.abs(Math.log(ratio / GOLDEN_RATIO));
  return Math.max(0, Math.min(10, 10 - logarithmicDistance * 10));
}

export function weightedScore(scores) {
  const weighted = Object.entries(SCORE_WEIGHTS).reduce((total, [key, weight]) => {
    const value = Number(scores[key]);
    if (!Number.isFinite(value) || value < 0 || value > 10) {
      throw new TypeError(`Invalid score for ${key}: ${scores[key]}`);
    }
    return total + value * weight;
  }, 0);
  return weighted / 100;
}

export function parseArgs(argv) {
  const values = {
    cdp: "http://127.0.0.1:9222",
    url: "http://127.0.0.1:8765/",
    out: ".hermes/audits/current",
    viewports: [390, 720, 1024, 1440, 1920],
    densities: ["compact", "comfortable", "spacious"],
    pages: [...DEFAULT_PAGES],
    height: 900,
    settleMs: 500,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    const next = argv[index + 1];
    if (key === "--help") values.help = true;
    else if (["--cdp", "--url", "--out"].includes(key) && next) {
      values[key.slice(2)] = next;
      index += 1;
    } else if (key === "--viewports" && next) {
      values.viewports = next.split(",").map(Number).filter((value) => Number.isInteger(value) && value >= 320);
      index += 1;
    } else if (key === "--densities" && next) {
      values.densities = next.split(",").map((value) => value.trim()).filter(Boolean);
      index += 1;
    } else if (key === "--pages" && next) {
      values.pages = next.split(",").map((value) => value.trim()).filter((value) => PAGE_IDS[value]);
      index += 1;
    } else if (key === "--height" && next) {
      values.height = Number(next);
      index += 1;
    } else if (key === "--settle-ms" && next) {
      values.settleMs = Number(next);
      index += 1;
    } else if (key.startsWith("--")) {
      throw new Error(`Unknown or incomplete option: ${key}`);
    }
  }
  if (!values.viewports.length) throw new Error("At least one viewport is required");
  if (!values.densities.length) throw new Error("At least one density is required");
  if (!values.pages.length) throw new Error("At least one known page is required");
  return values;
}

class CDPClient {
  constructor(webSocketUrl) {
    this.webSocketUrl = webSocketUrl;
    this.socket = null;
    this.nextId = 1;
    this.pending = new Map();
  }

  async connect() {
    await new Promise((resolve, reject) => {
      const socket = new WebSocket(this.webSocketUrl);
      this.socket = socket;
      socket.addEventListener("open", resolve, {once: true});
      socket.addEventListener("error", reject, {once: true});
      socket.addEventListener("message", (event) => {
        const message = JSON.parse(String(event.data));
        if (!message.id) return;
        const pending = this.pending.get(message.id);
        if (!pending) return;
        this.pending.delete(message.id);
        if (message.error) pending.reject(new Error(`${pending.method}: ${message.error.message}`));
        else pending.resolve(message.result || {});
      });
      socket.addEventListener("close", () => {
        for (const pending of this.pending.values()) pending.reject(new Error("CDP connection closed"));
        this.pending.clear();
      });
    });
  }

  send(method, params = {}) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return Promise.reject(new Error("CDP socket is not open"));
    }
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, {resolve, reject, method});
      this.socket.send(JSON.stringify({id, method, params}));
    });
  }

  close() {
    this.socket?.close();
  }
}

async function delay(milliseconds) {
  await new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function findPageTarget(cdpBase) {
  const response = await fetch(`${cdpBase.replace(/\/$/, "")}/json/list`);
  if (!response.ok) throw new Error(`Unable to read CDP targets (${response.status})`);
  const targets = await response.json();
  const page = targets.find((target) => target.type === "page" && target.webSocketDebuggerUrl);
  if (!page) throw new Error("No debuggable page target is available");
  return page;
}

export function buildPreparationExpression(pageName, density) {
  const pageId = PAGE_IDS[pageName] || pageName;
  return `(async () => {
    const pageButton = document.querySelector('[data-page="' + ${JSON.stringify(pageId)} + '"]');
    if (pageButton) pageButton.click();
    const densitySelect = document.querySelector('#density-select');
    if (densitySelect) {
      densitySelect.value = ${JSON.stringify(density)};
      densitySelect.dispatchEvent(new Event('change', {bubbles: true}));
    } else {
      document.body.dataset.density = ${JSON.stringify(density)};
    }
    const images = [...document.querySelectorAll('img')];
    images.forEach((image) => { image.loading = 'eager'; });
    if (document.fonts?.ready) await document.fonts.ready;
    await Promise.all(images.map((image) => image.complete && image.naturalWidth > 0 ? Promise.resolve() : image.decode().catch(() => undefined)));
    let freeze = document.querySelector('#obus-audit-freeze');
    if (!freeze) {
      freeze = document.createElement('style');
      freeze.id = 'obus-audit-freeze';
      freeze.textContent = '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}';
      document.head.append(freeze);
    }
    const auditWorkbench = document.querySelector('#terminal-workbench');
    auditWorkbench?.style.setProperty('--run-primary-fr', '1.61803398875fr');
    auditWorkbench?.style.setProperty('--run-secondary-fr', '1fr');
    document.querySelector('#run-workbench-splitter')?.setAttribute('aria-valuenow', '62');
    const activePanel = document.querySelector('.page.active[data-page-panel]');
    const foreignVisibleRoots = [...document.body.children].filter((element) => {
      if (element.matches('.shell,script,dialog,.toast,.setup,.access-overlay')) return false;
      const rect = element.getBoundingClientRect();
      const visible = typeof element.checkVisibility === 'function' ? element.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}) : getComputedStyle(element).display !== 'none';
      return visible && rect.width > 0 && rect.height > 0;
    }).length;
    return {
      buttonFound: Boolean(pageButton),
      panelVisible: Boolean(activePanel && getComputedStyle(activePanel).display !== 'none'),
      actualPageId: activePanel?.dataset.pagePanel || null,
      actualDensity: document.body.dataset.density || null,
      foreignVisibleRoots,
    };
  })()`;
}

function evaluationExpression(pageId, density) {
  return `(() => {
    const pageId = ${JSON.stringify(pageId)};
    const density = ${JSON.stringify(density)};

    const selectors = [
      'main', '.panel', '.panel-head', '.panel-body', '.terminal-workbench',
      '.terminal-block', '.shuffle-card', '.key-figure', '.key-meta', '.key-actions',
      'textarea', '.result', '.code-output', '.terminal-result', '.agent-context-text',
      'button', 'input', 'select', 'img', 'a[href]', 'summary', '[contenteditable="true"]',
      '[role="button"]', '[role="link"]', '[role="checkbox"]', '[role="radio"]', '[role="switch"]',
      '[role="tab"]', '[role="menuitem"]', '[role="separator"]'
    ];
    const intentionalOverlays = new Set(['DIALOG', 'MENU']);
    const nodes = [...new Set(selectors.flatMap((selector) => [...document.querySelectorAll(selector)]))]
      .filter((element) => {
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        const inViewport = rect.right >= 0 && rect.bottom >= 0 && rect.left <= innerWidth && rect.top <= innerHeight;
        return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) !== 0 && rect.width > 0 && rect.height > 0 && inViewport;
      });
    const describe = (element, index) => ({
      index,
      tag: element.tagName.toLowerCase(),
      id: element.id || null,
      classes: [...element.classList].slice(0, 5),
      role: element.getAttribute('role'),
      name: element.id || element.getAttribute('role') || element.tagName.toLowerCase(),
      rect: (() => { const rect = element.getBoundingClientRect(); return {x: rect.x, y: rect.y, width: rect.width, height: rect.height}; })(),
    });
    const records = nodes.map(describe);
    const overlapIndexes = nodes.map((element, index) => ({element, index}))
      .filter(({element}) => element.matches('img, button, input, select, textarea, .key-meta, .key-actions, .agent-info, .result, .code-output, .terminal-result, .agent-context-text, [role="separator"]'));
    const overlaps = [];
    for (let leftOffset = 0; leftOffset < overlapIndexes.length; leftOffset += 1) {
      for (let rightOffset = leftOffset + 1; rightOffset < overlapIndexes.length; rightOffset += 1) {
        const {element: left, index: leftIndex} = overlapIndexes[leftOffset];
        const {element: right, index: rightIndex} = overlapIndexes[rightOffset];
        if (left.contains(right) || right.contains(left)) continue;
        if (intentionalOverlays.has(left.tagName) || intentionalOverlays.has(right.tagName)) continue;
        if (left.closest('dialog,[role="menu"],[role="tooltip"]') || right.closest('dialog,[role="menu"],[role="tooltip"]')) continue;
        const a = records[leftIndex].rect;
        const b = records[rightIndex].rect;
        const width = Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x));
        const height = Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
        const area = width * height;
        if (area > 1) overlaps.push({left: records[leftIndex], right: records[rightIndex], area});
      }
    }

    const clipped = nodes.filter((element) => element.matches('textarea, .result, .code-output, .terminal-result, .agent-context-text, button, input, select, .key-meta, .key-actions, .agent-info, .panel-head'))
      .filter((element) => {
      const style = getComputedStyle(element);
      const scrollableX = ['auto', 'scroll'].includes(style.overflowX);
      const scrollableY = ['auto', 'scroll'].includes(style.overflowY);
      return (element.scrollWidth > element.clientWidth + 1 && !scrollableX) ||
        (element.scrollHeight > element.clientHeight + 1 && !scrollableY);
    }).map((element) => records[nodes.indexOf(element)]);

    const allImages = [...document.querySelectorAll('.page.active img, .side img, .top img')].filter((element) => {
      const style = getComputedStyle(element);
      const cssVisible = typeof element.checkVisibility === 'function'
        ? element.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})
        : style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) !== 0;
      return cssVisible;
    });
    const describeImage = (element) => {
      const rect = element.getBoundingClientRect();
      return {tag: 'img', id: element.id || null, classes: [...element.classList].slice(0, 5), role: null, name: 'img', rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}};
    };
    const brokenImages = allImages.filter((element) => !element.complete || element.naturalWidth <= 0 || element.naturalHeight <= 0 || element.getBoundingClientRect().width <= 0 || element.getBoundingClientRect().height <= 0).map(describeImage);
    const distortedImages = allImages.filter((element) => {
      const rect = element.getBoundingClientRect();
      if (!element.complete || element.naturalWidth <= 0 || element.naturalHeight <= 0 || rect.width <= 0 || rect.height <= 0) return false;
      return Math.abs(Math.log((rect.width / rect.height) / (element.naturalWidth / element.naturalHeight))) > .03 && getComputedStyle(element).objectFit === 'fill';
    }).map(describeImage);
    const interactiveSelector = 'button,input,select,textarea,a[href],summary,[contenteditable="true"],[role="button"],[role="link"],[role="checkbox"],[role="radio"],[role="switch"],[role="tab"],[role="menuitem"]';
    const undersizedTargets = nodes.filter((element) => element.matches(interactiveSelector))
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        return rect.width < 24 || rect.height < 24;
      }).map((element) => records[nodes.indexOf(element)]);
    const targetSizeAdvisories = nodes.filter((element) => element.matches(interactiveSelector))
      .filter((element) => { const rect = element.getBoundingClientRect(); return (rect.width < 40 || rect.height < 40) && rect.width >= 24 && rect.height >= 24; })
      .map((element) => records[nodes.indexOf(element)]);
    const invalidSeparators = nodes.filter((element) => element.getAttribute('role') === 'separator')
      .filter((element) => {
        const orientation = element.getAttribute('aria-orientation');
        const minimum = Number(element.getAttribute('aria-valuemin'));
        const maximum = Number(element.getAttribute('aria-valuemax'));
        const now = Number(element.getAttribute('aria-valuenow'));
        return !['horizontal','vertical'].includes(orientation) || ![minimum,maximum,now].every(Number.isFinite) || minimum > now || now > maximum;
      })
      .map((element) => records[nodes.indexOf(element)]);
    const horizontalOverflow = document.documentElement.scrollWidth > document.documentElement.clientWidth + 1;

    const ratioTarget = [...document.querySelectorAll('.terminal-workbench, .room-workspace, .adjustable-workspace')].find((element) => {
      const rect = element.getBoundingClientRect();
      const visible = typeof element.checkVisibility === 'function' ? element.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}) : getComputedStyle(element).display !== 'none';
      return visible && rect.width > 0 && rect.height > 0;
    }) || null;
    let primaryRatio = null;
    if (ratioTarget && ratioTarget.children.length >= 2) {
      const paneChildren = [...ratioTarget.children].filter((element) => element.getAttribute('role') !== 'separator' && getComputedStyle(element).display !== 'none');
      const first = paneChildren[0]?.getBoundingClientRect();
      const second = paneChildren[paneChildren.length - 1]?.getBoundingClientRect();
      if (first && second && Math.abs(first.y - second.y) <= 2 && first.width > 0 && second.width > 0) {
        primaryRatio = Math.max(first.width, second.width) / Math.min(first.width, second.width);
      }
    }

    return {
      pageId,
      density,
      document: {clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth},
      layoutState: {
        phoneMedia: matchMedia('(max-width: 720px)').matches,
        narrowMedia: matchMedia('(max-width: 960px)').matches,
        shellDisplay: getComputedStyle(document.querySelector('.shell')).display,
        shellColumns: getComputedStyle(document.querySelector('.shell')).gridTemplateColumns,
        workbenchColumns: ratioTarget ? getComputedStyle(ratioTarget).gridTemplateColumns : null,
      },
      counts: {auditedNodes: nodes.length, overlaps: overlaps.length, clipped: clipped.length, brokenImages: brokenImages.length, distortedImages: distortedImages.length, undersizedTargets: undersizedTargets.length, invalidSeparators: invalidSeparators.length},
      advisories: {targetsBelow40: targetSizeAdvisories.length},
      horizontalOverflow,
      primaryRatio,
      overlaps,
      clipped,
      brokenImages,
      distortedImages,
      undersizedTargets,
      targetSizeAdvisories,
      invalidSeparators,
    };
  })()`;
}

function slug(value) {
  return String(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export async function runAudit(options) {
  await mkdir(options.out, {recursive: true});
  const target = await findPageTarget(options.cdp);
  const client = new CDPClient(target.webSocketDebuggerUrl);
  await client.connect();
  const reports = [];
  try {
    await client.send("Page.enable");
    await client.send("Runtime.enable");
    await client.send("Network.enable");
    await client.send("Network.setCacheDisabled", {cacheDisabled: true});
    await client.send("Page.navigate", {url: options.url});
    await delay(effectiveSettleMs(options.settleMs));

    for (const width of options.viewports) {
      await client.send("Emulation.setDeviceMetricsOverride", deviceMetricsFor(width, options.height));
      await delay(options.settleMs);
      for (const density of options.densities) {
        for (const pageName of options.pages) {
          const pageId = PAGE_IDS[pageName];
          const prepared = await client.send("Runtime.evaluate", {
            expression: buildPreparationExpression(pageName, density),
            returnByValue: true,
            awaitPromise: true,
          });
          if (prepared.exceptionDetails) throw new Error(`Audit preparation failed for ${pageName}`);
          validatePreparationResult(prepared.result?.value, pageId, density);
          await delay(effectiveSettleMs(options.settleMs));
          const evaluated = await client.send("Runtime.evaluate", {
            expression: evaluationExpression(pageId, density),
            returnByValue: true,
            awaitPromise: true,
          });
          if (evaluated.exceptionDetails) throw new Error(`Audit evaluation failed for ${pageName}`);
          const report = evaluated.result?.value;
          if (!report) throw new Error(`No audit result for ${pageName}`);
          report.page = pageName;
          report.viewport = {width, height: options.height};
          report.goldenRatioScore = report.primaryRatio ? ratioScore(report.primaryRatio) : null;
          reports.push(report);

          const screenshot = await client.send("Page.captureScreenshot", {format: "png", fromSurface: true});
          const fileName = `${width}-${slug(density)}-${slug(pageName)}.png`;
          await writeFile(path.join(options.out, fileName), Buffer.from(screenshot.data, "base64"));
        }
      }
    }
  } finally {
    client.close();
  }

  const hardGateFailures = reports.reduce((total, report) => total +
    report.counts.overlaps + report.counts.clipped + report.counts.brokenImages + report.counts.distortedImages +
    report.counts.undersizedTargets + report.counts.invalidSeparators + (report.horizontalOverflow ? 1 : 0), 0);
  const stable = {
    schema: "obus-aui-visual-audit-v1",
    matrix: {pages: options.pages, viewports: options.viewports, densities: options.densities, height: options.height},
    hardGateFailures,
    reports,
  };
  await writeFile(path.join(options.out, "audit.json"), `${JSON.stringify(stable, null, 2)}\n`, "utf8");
  return stable;
}

function helpText() {
  return [
    "OBus AUI visual geometry audit",
    "",
    "Usage:",
    "  node tools/aui_visual_audit.mjs --cdp http://127.0.0.1:9222 --url http://127.0.0.1:8765/ --out .hermes/audits/current",
    "",
    "Options:",
    "  --viewports 390,720,1024,1440,1920",
    "  --densities compact,comfortable,spacious",
    `  --pages ${DEFAULT_PAGES.join(",")}`,
    "  --height 900",
    "  --settle-ms 500",
  ].join("\n");
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    console.log(helpText());
    return;
  }
  const result = await runAudit(options);
  console.log(JSON.stringify({schema: result.schema, hardGateFailures: result.hardGateFailures, reports: result.reports.length}));
  if (result.hardGateFailures > 0) process.exitCode = 2;
}

const invokedPath = process.argv[1] ? pathToFileURL(path.resolve(process.argv[1])).href : "";
if (import.meta.url === invokedPath) {
  main().catch((error) => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
  });
}
