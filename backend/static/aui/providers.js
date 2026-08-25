"use strict";

(function installObusProviders(root) {
  const builtIn = new Set(["key-local-ollama", "key-codex-oauth", "key-nous-oauth", "key-nvidia-nim", "key-anthropic", "key-google-gemini", "key-openrouter", "key-mistral", "key-groq", "key-xai", "key-together", "key-fireworks", "key-deepseek", "key-cerebras", "key-huggingface", "key-azure-openai"]);
  const OBusProviders = {
    create({api, state, $, $$, escapeHtml, formatTokens, toast, refresh, openKeyDialog, openKeySetup} = {}) {
      const render = (data) => {
        const element = $("#provider-list");
        if (!element || !data?.providers) return;
        element.innerHTML = data.providers.map((provider, index) => `<article class="key-card selectable shuffle-card" style="--shuffle-index:${index}" data-key-guide="${escapeHtml(provider.id)}"><figure class="key-figure"><img class="key-art" src="${escapeHtml(provider.sigil)}" alt="${provider.solomon_seal ? `Historical Solomon seal ${escapeHtml(provider.solomon_seal)} for ${escapeHtml(provider.name)}` : `Sigil for ${escapeHtml(provider.name)}`}"></figure><div class="key-meta"><h4>${escapeHtml(provider.symbol)} ${escapeHtml(provider.name)}</h4><p>Key service: ${escapeHtml(provider.provider)} · ${escapeHtml(provider.model)}</p><p class="context">${provider.solomon_seal ? `Solomon Key ${String(provider.solomon_seal_number).padStart(2, "0")} · ${escapeHtml(provider.solomon_seal)}` : "Custom Key sigil"}</p><p>${provider.solomon_seal_reason ? escapeHtml(provider.solomon_seal_reason) : ""}</p><p>Window: ${formatTokens(provider.max_context_tokens)} · ${escapeHtml(provider.state)} · ${escapeHtml(provider.status)}</p><p>Configured: ${provider.configured ? "yes" : "no"} · Verified: ${provider.verified ? "yes" : "no"}${provider.verified_at ? ` · ${escapeHtml(provider.verified_at)}` : ""}</p>${provider.last_probe_message ? `<p>${escapeHtml(provider.last_probe_message)}</p>` : ""}</div><div class="key-actions"><span class="badge ${provider.connected ? "ready" : "warn"}">${provider.connected ? "Ready now" : escapeHtml(provider.state)}</span><button class="button mini provider-test" data-key="${escapeHtml(provider.id)}">Test &amp; enable</button><button class="button mini key-edit" data-key="${escapeHtml(provider.id)}">Edit</button>${provider.solomon_seal_source ? `<a class="button mini" href="${escapeHtml(provider.solomon_seal_source)}" target="_blank" rel="noopener">Seal source</a>` : ""}${provider.id.startsWith("key-") && !builtIn.has(provider.id) ? `<button class="button mini danger key-delete" data-key="${escapeHtml(provider.id)}">Delete</button>` : "<span class=\"badge\">Built-in</span>"}</div></article>`).join("");
      };
      const bind = (data = state.dashboard) => {
        $$(".provider-test").forEach((button) => {
          button.onclick = async () => {
            const original = button.textContent; button.disabled = true; button.textContent = "Testing…";
            try {
              const output = await api(`/api/providers/${encodeURIComponent(button.dataset.key)}/test`, {method: "POST"});
              await refresh();
              const message = output.success ? (output.state === "disabled" ? "Verified successfully; Key remains disabled" : "Live probe succeeded — Key is Ready") : (output.message || "Live probe failed; Key remains Staged");
              toast(message, !output.success);
            } catch (error) { toast(error.message, true); }
            finally { button.disabled = false; button.textContent = original; }
          };
        });
        $$(".key-edit").forEach((button) => { button.onclick = () => openKeyDialog(data?.providers?.find((provider) => provider.id === button.dataset.key)); });
        $$('[data-key-guide]').forEach((card) => { card.onclick = (event) => { if (event.target.closest("button,a,select")) return; openKeySetup(data?.providers?.find((provider) => provider.id === card.dataset.keyGuide)); }; });
        $$(".key-delete").forEach((button) => {
          button.onclick = async () => {
            const key = data?.providers?.find((provider) => provider.id === button.dataset.key);
            if (!key || !root.confirm(`Delete ${key.name}? Cards pinned to it will return to Auto.`)) return;
            try { await api(`/api/keys/${encodeURIComponent(button.dataset.key)}`, {method: "DELETE"}); await refresh(); toast("Key deleted"); }
            catch (error) { toast(error.message, true); }
          };
        });
      };
      return {render, bind};
    },
  };
  root.OBusProviders = OBusProviders;
})(window);
