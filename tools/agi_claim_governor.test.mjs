import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import test from "node:test";

const SOURCE = readFileSync(
  new URL("../backend/static/aui/agi-claim.js", import.meta.url),
  "utf8",
);

function functionSource(name, nextName) {
  const start = SOURCE.indexOf(`function ${name}(`);
  const end = nextName ? SOURCE.indexOf(`function ${nextName}(`, start + 1) : -1;
  assert.notEqual(start, -1, `expected ${name} to exist`);
  assert.notEqual(end, -1, `expected ${nextName} after ${name}`);
  return SOURCE.slice(start, end);
}

test("improvement governor mounts its operator controls", () => {
  assert.match(SOURCE, /function ensureImprovementGovernorSurface\(/);
  assert.match(SOURCE, /function renderImprovementGovernor\(/);
  assert.match(SOURCE, /function startOneImprovementLoop\(/);
  assert.match(SOURCE, /function runImprovementEvidenceCandidate\(/);
});

test("failed start preserves the journal-integrity announcement", () => {
  const startLoop = functionSource("startOneImprovementLoop", "refreshAgiClaimStatus");
  const failure = startLoop.indexOf("if (!response.ok)");
  const announcement = startLoop.indexOf("announceImprovementGovernor", failure);

  assert.notEqual(failure, -1, "a failed start response must be handled");
  assert.ok(
    announcement > failure,
    "the failed-start branch must announce the server-provided, journal-integrity-safe reason",
  );
});
