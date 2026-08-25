import test from "node:test";
import assert from "node:assert/strict";

import {
  buildPreparationExpression,
  deviceMetricsFor,
  effectiveSettleMs,
  GOLDEN_RATIO,
  imageGeometryIssue,
  isRectInViewport,
  isInvalidSeparator,
  layoutRatio,
  overlapArea,
  paneLayoutRatio,
  ratioScore,
  validatePreparationResult,
  weightedScore,
} from "./aui_visual_audit.mjs";


test("nested elements are not reported as sibling overlap", () => {
  const outer = {x: 0, y: 0, width: 100, height: 100};
  const inner = {x: 10, y: 10, width: 20, height: 20};
  assert.equal(overlapArea(outer, inner, {nested: true}), 0);
});


test("unrelated overlapping rectangles report intersection area", () => {
  const left = {x: 0, y: 0, width: 20, height: 20};
  const right = {x: 10, y: 10, width: 20, height: 20};
  assert.equal(overlapArea(left, right), 100);
});


test("touching edges are not overlap", () => {
  const left = {x: 0, y: 0, width: 20, height: 20};
  const right = {x: 20, y: 0, width: 20, height: 20};
  assert.equal(overlapArea(left, right), 0);
});


test("viewport filtering keeps partial elements and rejects offscreen lazy assets", () => {
  assert.equal(isRectInViewport({x: 10, y: 890, width: 20, height: 20}, 1024, 900), true);
  assert.equal(isRectInViewport({x: 10, y: 901, width: 20, height: 20}, 1024, 900), false);
  assert.equal(isRectInViewport({x: -25, y: 20, width: 20, height: 20}, 1024, 900), false);
});


test("desktop AUI viewport audit does not emulate a mobile browser", () => {
  assert.deepEqual(deviceMetricsFor(390, 900), {
    width: 390,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false,
  });
});


test("audit waits for bounded deal motion to finish before measuring", () => {
  assert.equal(effectiveSettleMs(300), 800);
  assert.equal(effectiveSettleMs(1200), 1200);
});


test("page preparation happens before measurement and eagerly loads visible art", () => {
  const expression = buildPreparationExpression("agents", "comfortable");
  assert.match(expression, /data-page/);
  assert.match(expression, /comfortable/);
  assert.match(expression, /loading = 'eager'/);
  assert.match(expression, /image\.decode/);
  assert.match(expression, /actualPageId/);
  assert.match(expression, /actualDensity/);
  assert.match(expression, /document\.fonts\.ready/);
  assert.match(expression, /foreignVisibleRoots/);
  assert.match(expression, /1\.61803398875fr/);
  assert.match(expression, /checkVisibility/);
});


test("preparation result rejects missing or mislabeled state", () => {
  assert.throws(() => validatePreparationResult({buttonFound: false}, "agents", "comfortable"), /button/i);
  assert.throws(() => validatePreparationResult({buttonFound: true, actualPageId: "dashboard", actualDensity: "compact"}, "agents", "comfortable"), /mismatch/i);
  assert.throws(() => validatePreparationResult({buttonFound: true, panelVisible: true, actualPageId: "agents", actualDensity: "comfortable", foreignVisibleRoots: 1}, "agents", "comfortable"), /foreign/i);
  assert.doesNotThrow(() => validatePreparationResult({buttonFound: true, panelVisible: true, actualPageId: "agents", actualDensity: "comfortable"}, "agents", "comfortable"));
});


test("zero-size and distorted images are hard geometry issues", () => {
  assert.equal(imageGeometryIssue({complete: true, naturalWidth: 0, naturalHeight: 0, width: 0, height: 0}), "broken");
  assert.equal(imageGeometryIssue({complete: true, naturalWidth: 400, naturalHeight: 200, width: 100, height: 100}), "distorted");
  assert.equal(imageGeometryIssue({complete: true, naturalWidth: 400, naturalHeight: 200, width: 200, height: 100}), null);
});


test("separator semantics validate orientation and bounded values", () => {
  assert.equal(isInvalidSeparator({orientation: "diagonal", minimum: 0, now: 50, maximum: 100}), true);
  assert.equal(isInvalidSeparator({orientation: "vertical", minimum: 75, now: 50, maximum: 45}), true);
  assert.equal(isInvalidSeparator({orientation: "horizontal", minimum: 0, now: 50, maximum: 100}), false);
});


test("golden ratio receives a perfect score without rounding", () => {
  assert.equal(ratioScore(GOLDEN_RATIO), 10);
  assert.ok(ratioScore(1.5) < 10);
});


test("golden ratio is measured only for side-by-side panes", () => {
  const primary = {x: 0, y: 0, width: 618, height: 600};
  const rail = {x: 631, y: 0, width: 382, height: 600};
  assert.ok(Math.abs(layoutRatio(primary, rail) - GOLDEN_RATIO) < 0.001);
  assert.equal(layoutRatio(primary, {...rail, x: 0, y: 620}), null);
});


test("splitter geometry is excluded from pane ratio", () => {
  const items = [
    {role: null, rect: {x: 0, y: 0, width: 618, height: 600}},
    {role: "separator", rect: {x: 618, y: 0, width: 13, height: 600}},
    {role: null, rect: {x: 631, y: 0, width: 382, height: 600}},
  ];
  assert.ok(Math.abs(paneLayoutRatio(items) - GOLDEN_RATIO) < 0.001);
});


test("weighted score uses the declared percentages", () => {
  const scores = {
    geometry: 10,
    typography: 9,
    goldenRatio: 10,
    spacing: 10,
    responsive: 10,
    accessibility: 10,
    adjustability: 10,
    identity: 10,
    polish: 10,
    stability: 10,
  };
  assert.equal(weightedScore(scores), 9.88);
});


test("weighted score never rounds a sub-threshold value up to 9.90", () => {
  const scores = Object.fromEntries(Object.keys({geometry: 1, typography: 1, goldenRatio: 1, spacing: 1, responsive: 1, accessibility: 1, adjustability: 1, identity: 1, polish: 1, stability: 1}).map((key) => [key, 9.89995]));
  assert.ok(weightedScore(scores) < 9.9);
});
