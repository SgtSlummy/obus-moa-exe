(function exposeOllamaPresets(global) {
  "use strict";

  const OBLITERATUS_QWEN_MODEL = "hf.co/OBLITERATUS/Qwen3.8-27B-OBLITERATED:Q4_K_M";
  const OBLITERATUS_QWEN_PRESET = Object.freeze({
    model: OBLITERATUS_QWEN_MODEL,
    label: "Qwen3.8 27B OBLITERATED (Q4_K_M)",
    // Verified on the RTX 3090: 65K keeps the entire Qwen profile on GPU.
    context: 65536,
  });
  const PRESETS = Object.freeze([OBLITERATUS_QWEN_PRESET]);

  function modelName(value) {
    if (typeof value === "string") return value.trim();
    if (!value || typeof value !== "object") return "";
    for (const key of ["model", "name", "id"]) {
      if (typeof value[key] === "string" && value[key].trim()) {
        return value[key].trim();
      }
    }
    return "";
  }

  function canonicalModelName(value) {
    const name = modelName(value).replace(/\\/g, "/").toLowerCase();
    return name.endsWith(":latest") ? name.slice(0, -":latest".length) : name;
  }

  function presetFor(value) {
    const key = canonicalModelName(value);
    return PRESETS.find((preset) => canonicalModelName(preset.model) === key) || null;
  }

  function isInstalled(selectedModel, installedModels) {
    const selectedKey = canonicalModelName(selectedModel);
    if (!selectedKey) return false;
    return (Array.isArray(installedModels) ? installedModels : []).some(
      (candidate) => canonicalModelName(candidate) === selectedKey,
    );
  }

  function mergeModelOptions(installedModels, currentSelection) {
    const installed = Array.isArray(installedModels) ? installedModels : [];
    const installedKeys = new Set(installed.map(canonicalModelName).filter(Boolean));
    const selectedKey = canonicalModelName(currentSelection);
    const options = [];
    const indexes = new Map();

    function add(candidate) {
      const candidateModel = modelName(candidate);
      const key = canonicalModelName(candidateModel);
      if (!key) return;

      const preset = presetFor(candidateModel);
      const source = candidate && typeof candidate === "object" ? candidate : {};
      const existingIndex = indexes.get(key);
      const next = {
        model: preset ? preset.model : candidateModel,
        label:
          (preset && preset.label) ||
          (typeof source.label === "string" && source.label.trim()) ||
          candidateModel,
        context:
          (preset && preset.context) ||
          (Number.isFinite(Number(source.context)) ? Number(source.context) : null),
        preset: Boolean(preset),
        installed: installedKeys.has(key),
        selected: Boolean(selectedKey && selectedKey === key),
      };

      if (existingIndex === undefined) {
        indexes.set(key, options.length);
        options.push(next);
        return;
      }

      const existing = options[existingIndex];
      options[existingIndex] = {
        ...existing,
        label: existing.preset ? existing.label : next.label,
        context: existing.context == null ? next.context : existing.context,
        preset: existing.preset || next.preset,
        installed: existing.installed || next.installed,
        selected: existing.selected || next.selected,
      };
    }

    PRESETS.forEach(add);
    installed.forEach(add);
    add(currentSelection);
    return options;
  }

  function getReadiness({ online = false, installedModels = [], selectedModel = "" } = {}) {
    const model = modelName(selectedModel);

    if (!online) {
      return {
        state: "offline",
        ready: false,
        message: "Ollama is offline or unreachable. Start Ollama, then refresh model readiness.",
        command: null,
      };
    }

    if (!model) {
      return {
        state: "missing",
        ready: false,
        message: "Select an Ollama model to check whether it is ready.",
        command: null,
      };
    }

    if (isInstalled(model, installedModels)) {
      return {
        state: "ready",
        ready: true,
        message: `The selected model is installed and ready: ${model}.`,
        command: null,
      };
    }

    const command = `ollama pull ${model}`;
    return {
      state: "missing",
      ready: false,
      message: `The selected model has not been pulled yet. Run: ${command}`,
      command,
    };
  }

  global.OBusOllamaPresets = Object.freeze({
    OBLITERATUS_QWEN_MODEL,
    OBLITERATUS_QWEN_PRESET,
    PRESETS,
    canonicalModelName,
    isInstalled,
    mergeModelOptions,
    getReadiness,
  });
})(window);
