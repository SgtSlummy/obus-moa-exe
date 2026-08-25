import test from "node:test";
import assert from "node:assert/strict";

import {
  buildPreparationExpression,
  GOLDEN_RATIO,
  isRectInViewport,
  overlapArea,
  ratioScore,
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


test("page preparation happens before measurement and eagerly loads visible art", () => {
  const expression = buildPreparationExpression("agents", "comfortable");
  assert.match(expression, /data-page/);
  assert.match(expression, /comfortable/);
  assert.match(expression, /loading = 'eager'/);
});


test("golden ratio receives a perfect score without rounding", () => {
  assert.equal(ratioScore(GOLDEN_RATIO), 10);
  assert.ok(ratioScore(1.5) < 10);
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
