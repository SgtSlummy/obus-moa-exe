"use strict";

(function installObusPlan(root) {
  const OBusPlan = {
    create({api, $, escapeHtml, toast, setPage, loadRooms, loadThreads, announce} = {}) {
      const render = (result) => {
        const deliberation = result?.deliberation || {};
        const packets = deliberation.packets || [];
        const roomIds = deliberation.room_ids || [];
        const flow = $("#plan-flow");
        const resultOutput = $("#plan-result");
        const status = $("#plan-status");
        if (status) {
          status.textContent = packets.length ? `Complete · ${packets.length} room decisions` : "Ready";
          status.className = `badge ${packets.length ? "ready" : "warn"}`;
        }
        if (flow) {
          flow.innerHTML = [
            `<article class="plan-node plan-node-goal"><span>Goal</span><strong>${escapeHtml(result?.prompt || "Planning goal")}</strong><small>Independent proposals begin here</small></article>`,
            ...roomIds.map((roomId, index) => {
              const packet = packets[index] || {};
              return `<article class="plan-node plan-node-room"><span>Room ${index + 1}</span><strong>${escapeHtml(roomId)}</strong><small>${escapeHtml(packet.confidence || "pending")} confidence · ${escapeHtml(packet.status || "deliberating")}</small></article>`;
            }),
            `<article class="plan-node plan-node-synthesis"><span>Chymeria synthesis</span><strong>Review before execution</strong><small>Planning only · no tools were executed</small></article>`,
          ].join("");
        }
        if (resultOutput) {
          resultOutput.className = `result ${packets.length ? "" : "empty"}`;
          resultOutput.textContent = packets.length
            ? packets.map((packet, index) => [
              `Room ${index + 1} · ${packet.confidence || "unknown"} confidence · ${packet.status || "provisional"}`,
              packet.position || "No decision packet returned.",
              packet.rationale ? `Rationale: ${packet.rationale}` : "",
              packet.unresolved_questions?.length ? `Open questions: ${packet.unresolved_questions.join("; ")}` : "",
            ].filter(Boolean).join("\n")).join("\n\n────\n\n")
            : "No plan has been deliberated yet.";
        }
      };

      const loadAutoDeliberation = async () => {
        const value = await api("/api/settings/auto-deliberation");
        const toggle = $("#plan-auto-toggle");
        if (toggle) toggle.checked = !!value.enabled;
        return value;
      };

      const setAutoDeliberation = async (enabled) => {
        const value = await api("/api/settings/auto-deliberation", {
          method: "PUT",
          body: JSON.stringify({enabled: !!enabled}),
        });
        const toggle = $("#plan-auto-toggle");
        if (toggle) toggle.checked = !!value.enabled;
        announce?.(value.enabled
          ? "Eligible Hermes routes will now receive bounded parallel planning evidence."
          : "Automatic route deliberation is disabled.");
        return value;
      };

      const run = async () => {
        const input = $("#plan-input");
        const button = $("#plan-run");
        const status = $("#plan-status");
        const prompt = input?.value.trim();
        if (!prompt) {
          toast("Enter a planning goal first", true);
          input?.focus();
          return;
        }
        button.disabled = true;
        button.textContent = "Deliberating…";
        status.textContent = "Parallel rooms deliberating";
        status.className = "badge warn";
        $("#plan-result").className = "result";
        $("#plan-result").textContent = "Creating independent room proposals, then synthesizing sanitized decision packets…";
        try {
          const result = await api("/api/plan/deliberate", {
            method: "POST",
            body: JSON.stringify({prompt, mode: $("#plan-mode").value}),
          });
          render(result);
          await Promise.all([loadRooms?.(), loadThreads?.()]);
          announce?.("Parallel plan deliberation complete; review the room decisions before execution.");
          toast("Plan deliberation complete");
          return result;
        } catch (error) {
          status.textContent = "Plan failed";
          status.className = "badge warn";
          $("#plan-result").className = "result empty";
          $("#plan-result").textContent = error.message;
          announce?.(`Plan deliberation failed: ${error.message}`, true);
          toast(error.message, true);
          throw error;
        } finally {
          button.disabled = false;
          button.textContent = "Deliberate plan";
        }
      };

      const open = () => {
        setPage("plan");
        $("#plan-input")?.focus();
      };

      return {open, render, run, loadAutoDeliberation, setAutoDeliberation};
    },
  };
  root.OBusPlan = OBusPlan;
})(window);
