import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const moduleUrl = new URL("../backend/static/aui/ollama-presets.js", import.meta.url);
const moduleSource = readFileSync(moduleUrl, "utf8");

function loadApi() {
  const context = vm.createContext({ window: {} });
  new vm.Script(moduleSource, { filename: moduleUrl.pathname }).runInContext(context);
  return context.window.OBusOllamaPresets;
}

const api = loadApi();
const model = "hf.co/OBLITERATUS/Qwen3.8-27B-OBLITERATED:Q4_K_M";

test("exports an always-selectable OBLITERATUS Qwen preset", () => {
  assert.ok(api);
  assert.equal(api.OBLITERATUS_QWEN_PRESET.model, model);
  assert.equal(api.OBLITERATUS_QWEN_PRESET.context, 65536);
  assert.match(api.OBLITERATUS_QWEN_PRESET.label, /Qwen3\.8 27B OBLITERATED/);

  const options = api.mergeModelOptions([], model);
  const preset = options.find((option) => option.model === model);
  assert.ok(preset);
  assert.equal(preset.preset, true);
  assert.equal(preset.installed, false);
  assert.equal(preset.selected, true);
});

test("dedupes canonical, case, and latest model variants", () => {
  const options = api.mergeModelOptions(
    ["granite3.3", { name: "GRANITE3.3:latest" }, { model: "Granite3.3" }],
    "granite3.3:latest",
  );
  const matches = options.filter(
    (option) => api.canonicalModelName(option.model) === "granite3.3",
  );

  assert.equal(api.canonicalModelName("GRANITE3.3:latest"), "granite3.3");
  assert.equal(matches.length, 1);
  assert.equal(matches[0].installed, true);
  assert.equal(matches[0].selected, true);
});

test("reports offline readiness before model availability", () => {
  const readiness = api.getReadiness({
    online: false,
    installedModels: [model],
    selectedModel: model,
  });

  assert.equal(readiness.state, "offline");
  assert.equal(readiness.ready, false);
  assert.match(readiness.message, /Ollama is offline or unreachable/);
  assert.equal(readiness.command, null);
});

test("explains how to pull a selected model that is missing", () => {
  const readiness = api.getReadiness({
    online: true,
    installedModels: [],
    selectedModel: model,
  });
  const command = `ollama pull ${model}`;

  assert.equal(readiness.state, "missing");
  assert.equal(readiness.ready, false);
  assert.equal(readiness.command, command);
  assert.match(readiness.message, /selected model has not been pulled yet/i);
  assert.ok(readiness.message.includes(command));
});

test("reports a canonically matching installed model as ready", () => {
  const readiness = api.getReadiness({
    online: true,
    installedModels: [{ name: model.toUpperCase() }],
    selectedModel: model,
  });

  assert.equal(readiness.state, "ready");
  assert.equal(readiness.ready, true);
  assert.match(readiness.message, /installed and ready/);
  assert.equal(readiness.command, null);
});
