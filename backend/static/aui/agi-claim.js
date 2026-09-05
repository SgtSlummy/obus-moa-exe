(() => {
  "use strict";

  function setText(id, value) {
    const element = document.getElementById(id);
    if (element) element.textContent = String(value || "");
  }

  function formatScore(value) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? `${numeric.toFixed(1)}%` : "—";
  }

  function renderBaselineStatus(baseline) {
    const latest = baseline.latest_report || null;
    if (!latest) {
      setText("agi-baseline-state", baseline.status === "unavailable" ? "Unavailable" : "Not run");
      setText(
        "agi-baseline-summary",
        `${baseline.probe_count || 6} frozen synthetic probes run ${baseline.default_repeats || 3} times across local Qwen and the configured OmniRoute Mimo free route.`
      );
      setText(
        "agi-baseline-gap",
        "Run the bounded comparison to measure a reproducible development baseline and reveal the next category gap."
      );
      setText(
        "agi-baseline-limits",
        "Descriptive development evidence only; this public suite cannot earn or promote the Autonomous AGI claim."
      );
      return;
    }

    const comparison = latest.comparison || {};
    const gap = comparison.next_improvement_gap || {};
    const local = formatScore(comparison.local_score_percent);
    const external = formatScore(comparison.external_score_percent);
    setText(
      "agi-baseline-state",
      comparison.measurement_valid ? "Measured · descriptive" : "Incomplete"
    );
    setText(
      "agi-baseline-summary",
      `Local Qwen ${local} · OmniRoute Mimo free ${external} · ${latest.repeats || 1} run${latest.repeats === 1 ? "" : "s"} per probe.`
    );
    setText(
      "agi-baseline-gap",
      gap.category
        ? `Next measured gap: ${gap.category} · local ${formatScore(gap.local_score)} · external ${formatScore(gap.external_score)}.`
        : "No category gap is available from the latest receipt."
    );
    setText(
      "agi-baseline-limits",
      "Every response is scored by exact or JSON equality, with model identity, latency, errors, configuration, and content digests receipted. The result never changes AGI attainment."
    );
  }

  function renderAgiClaim(payload) {
    const claim = payload.target_claim || {};
    const evidence = payload.evidence || {};
    const improvement = payload.guarded_improvement || {};
    const baseline = payload.measured_baseline || {};
    const counts = evidence.gate_counts || {};
    const gates = Array.isArray(evidence.gates) ? evidence.gates : [];
    const ladder = Array.isArray(claim.ladder) ? claim.ladder : [];
    const ladderLevels = new Set(
      ladder.map((entry) => entry && entry.level).filter((level) => typeof level === "string")
    );
    const gateIds = gates
      .map((gate) => gate && gate.id)
      .filter((gateId) => typeof gateId === "string" && gateId.length > 0);
    const currentLevel = typeof claim.current_level === "string" ? claim.current_level : "";
    const targetLevel = typeof claim.target_level === "string" ? claim.target_level : "";
    const reportedLevel = typeof evidence.reported_level === "string"
      ? evidence.reported_level
      : "";
    const requiredGateCount = Number(evidence.required_gate_count);
    const authorizationComplete =
      claim.claim_permitted === true &&
      evidence.qualification === "earned" &&
      evidence.overall_status === "passed" &&
      evidence.receipt_provenance_present === true &&
      reportedLevel === targetLevel &&
      Number(counts.passed) === 23 &&
      Number(counts.failed) === 0 &&
      Number(counts.incomplete) === 0 &&
      gates.every((gate) => gate && gate.status === "passed");
    const contractValid =
      payload.schema_version === 2 &&
      claim.version === "2.0.0" &&
      targetLevel === "A23" &&
      claim.gate_count === 23 &&
      requiredGateCount === 23 &&
      gates.length === 23 &&
      gateIds.length === 23 &&
      new Set(gateIds).size === 23 &&
      currentLevel === reportedLevel &&
      (currentLevel !== targetLevel || authorizationComplete) &&
      ladderLevels.has(currentLevel) &&
      ladderLevels.has(targetLevel) &&
      evidence.api_submission_can_authorize === false;
    const attained = contractValid && authorizationComplete;
    const unresolved = gates
      .filter((gate) => gate && gate.status !== "passed")
      .slice(0, 4)
      .map((gate) => gate.title || gate.id)
      .filter(Boolean);

    if (!contractValid) {
      setText("agi-claim-state", "Status unavailable — claim not permitted");
      setText("agi-claim-verified", "Verified level: unavailable");
      setText("agi-claim-target", "Research target: unavailable");
      setText("agi-claim-attainment", "A23 attainment: not permitted");
      setText(
        "agi-claim-definition",
        "The A23 contract is missing, malformed, or inconsistent; the claim fails closed."
      );
      setText(
        "agi-claim-evidence",
        "A valid v2.0.0 manifest with exactly 23 unique gates is required before evidence can be shown."
      );
      setText("agi-claim-blockers", "Restore the versioned evidence contract, then refresh.");
    } else {
      setText("agi-claim-state", attained ? "A23 · attained" : "A23 · not attained");
      setText("agi-claim-verified", `Verified level: ${attained ? targetLevel : currentLevel}`);
      setText("agi-claim-target", `Research target: ${targetLevel}`);
      setText("agi-claim-attainment", `A23 attainment: ${attained ? "Attained" : "Not attained"}`);
      setText("agi-claim-definition", claim.definition);
      setText(
        "agi-claim-evidence",
        `${claim.claim_statement || "Claim evidence is unavailable."} ` +
          `${Number(counts.passed) || 0}/23 gates pass; ` +
          `${evidence.required_primary_runs || 0} sealed primary runs and ` +
          `${evidence.required_independent_replications || 0} independent organizational replication required. ` +
          `Contract v${claim.version}; manifest ${String(evidence.manifest_digest || "unavailable").slice(0, 12)}. ` +
          "API receipts are screening-only; external artifact rehash and authenticated independent attestation are required."
      );
      setText(
        "agi-claim-blockers",
        attained
          ? "All 23 gates and the independent evidence envelope are satisfied."
          : unresolved.length
            ? `Next unresolved gates: ${unresolved.join(" · ")}`
            : "Claim permission and independent receipt provenance remain unresolved."
      );
    }
    setText(
      "agi-improvement-policy",
      improvement.statement || "Guarded improvement policy is unavailable."
    );
    setText(
      "agi-improvement-authority",
      `Lifecycle: ${(improvement.lifecycle || []).join(" → ")}. ` +
        `Human-only: ${(improvement.human_only_actions || []).join(", ")}. ` +
        `Minimum ${Math.round((improvement.minimum_candidate_delta || 0) * 100)}-point ` +
        `objective gain across ${improvement.minimum_reproducible_runs || 0} reproducible runs, ` +
        "with held-out, safety, regression, contract, monitoring, and tested-rollback evidence."
    );
    renderBaselineStatus(baseline);
  }

  function renderEpistemicPolicy(payload) {
    const enabled = Boolean(payload?.enabled);
    const version = String(payload?.version || "unknown");
    const state = enabled ? "Active" : "Operator disabled";
    const guard = payload?.deterministic_guard || {};
    const guardState = guard.status === "active"
      ? "Deterministic private-state guard active"
      : "Deterministic guard disabled";
    const rollbackVariable = String(
      payload?.rollback?.environment_variable || "OBUS_EPISTEMIC_POLICY"
    );
    setText(
      "agi-epistemic-summary",
      `v${version} · ${state} · ${guardState} · rollback via ${rollbackVariable}=off`
    );
    setText(
      "agi-epistemic-limitation",
      String(payload?.known_limitation || "A prompt policy is not a calibration guarantee.")
    );
    setText(
      "agi-epistemic-promotion",
      "No AGI promotion: this policy does not earn or promote the Autonomous AGI claim."
    );
    setText("agi-epistemic-state", state);
  }

  async function refreshEpistemicPolicyStatus() {
    setText("agi-epistemic-state", "Checking…");
    try {
      const response = await fetch("/api/agi/epistemic/policy", {
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`Epistemic policy status failed (${response.status})`);
      renderEpistemicPolicy(await response.json());
    } catch {
      setText("agi-epistemic-summary", "Policy status is temporarily unavailable.");
      setText(
        "agi-epistemic-limitation",
        "The runtime could not verify the policy or its rollback state."
      );
      setText(
        "agi-epistemic-promotion",
        "No AGI promotion: unavailable policy evidence cannot earn or promote the Autonomous AGI claim."
      );
      setText("agi-epistemic-state", "Unavailable");
    }
  }

  let governorRefreshPromise = null;
  let governorStartPromise = null;
  let governorStartIdempotencyKey = "";

  function copyGovernorClassName(target, source) {
    const className = source?.getAttribute?.("class");
    if (className) target.setAttribute("class", className);
  }

  function humanizeGovernorValue(value) {
    const normalized = String(value || "unknown").replace(/_/g, " ").trim();
    return normalized.charAt(0).toUpperCase() + normalized.slice(1);
  }

  function shortGovernorDigest(value) {
    const raw = typeof value === "string" ? value.trim() : "";
    if (!raw) return "not available";
    const normalized = raw.startsWith("sha256:") ? raw.slice(7) : raw;
    return normalized.length > 12 ? `${normalized.slice(0, 12)}…` : normalized;
  }

  function formatGovernorNumber(value) {
    if (value === null || value === undefined || value === "") return "";
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return "";
    return Number.isInteger(numeric)
      ? String(numeric)
      : numeric.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
  }

  function formatGovernorObjective(objective) {
    if (typeof objective === "string" && objective.trim()) {
      return `${objective.trim()} · legacy unstructured objective`;
    }
    if (!objective || typeof objective !== "object") return "No objective recorded.";
    const path = String(objective.path || "Measured objective");
    const details = [];
    const gap = formatGovernorNumber(objective.gap);
    const value = formatGovernorNumber(objective.value);
    const target = formatGovernorNumber(objective.target);
    if (gap) details.push(`highest gap ${gap}`);
    if (value) details.push(`current ${value}`);
    if (target) details.push(`${String(objective.direction || "target")} ${target}`);
    return details.length
      ? `${path} · ${details.join(" · ")}`
      : `${path} · awaiting quantifiable evidence`;
  }

  function formatGovernorCheckpoint(checkpoint) {
    if (typeof checkpoint === "string") return shortGovernorDigest(checkpoint);
    if (!checkpoint || typeof checkpoint !== "object") return "Not available";
    const digest =
      checkpoint.digest ||
      checkpoint.checkpoint_digest ||
      checkpoint.baseline_digest ||
      checkpoint.id ||
      "";
    const status = checkpoint.status ? humanizeGovernorValue(checkpoint.status) : "";
    const shortDigest = shortGovernorDigest(digest);
    return status ? `${status} · ${shortDigest}` : shortDigest;
  }

  function formatGovernorNextAction(value) {
    const labels = {
      start_loop: "Start a bounded improvement loop.",
      screen_candidate: "Screen the candidate against the recorded objective.",
      await_human_authorization: "Await human authorization; this interface cannot authorize or promote.",
      start_new_loop: "Start another bounded loop when ready.",
      selection_required: "No eligible loop is selected by the measured baseline.",
      no_measured_local_deficit: "No measured local deficit selects a new loop.",
      none: "No automated action is available.",
      investigate_journal_integrity: "Investigate journal integrity before any loop can start.",
    };
    return labels[value] || humanizeGovernorValue(value);
  }

  function appendGovernorFact(list, label, id) {
    const term = document.createElement("dt");
    term.textContent = label;
    const value = document.createElement("dd");
    value.id = id;
    value.textContent = "—";
    list.append(term, value);
  }

  function appendImprovementGovernorEvidencePanels(surface, nearbyFacts) {
    const evidenceDetails = document.createElement("details");
    evidenceDetails.id = "agi-improvement-governor-evidence";
    const evidenceSummary = document.createElement("summary");
    evidenceSummary.id = "agi-improvement-governor-evidence-summary";
    evidenceSummary.textContent = "Candidate evidence · not run";
    evidenceDetails.appendChild(evidenceSummary);
    const evidenceFacts = document.createElement("dl");
    evidenceFacts.id = "agi-improvement-governor-evidence-facts";
    copyGovernorClassName(evidenceFacts, nearbyFacts);
    appendGovernorFact(evidenceFacts, "Receipt", "agi-improvement-governor-receipt");
    appendGovernorFact(evidenceFacts, "Isolation", "agi-improvement-governor-isolation");
    appendGovernorFact(evidenceFacts, "Probes", "agi-improvement-governor-probes");
    appendGovernorFact(evidenceFacts, "Warm target", "agi-improvement-governor-warm-target");
    const warmTargetNote = document.createElement("p");
    warmTargetNote.id = "agi-improvement-governor-warm-target-note";
    warmTargetNote.textContent = "Historical record only: this retired 262,144-context legacy candidate is invalid and is not the active Local Ollama runtime. It carries no A23 credit.";
    evidenceDetails.appendChild(evidenceFacts);
    evidenceDetails.appendChild(warmTargetNote);
    const handoffActions = document.createElement("div");
    handoffActions.id = "agi-campaign-envelope-actions";
    const handoffButton = document.createElement("button");
    handoffButton.id = "agi-campaign-envelope-download";
    handoffButton.type = "button";
    handoffButton.className = "button mini";
    handoffButton.textContent = "Download A23 verifier handoff";
    handoffButton.title = "Downloads a planning envelope for an external evaluator; it cannot promote A23.";
    const handoffNotice = document.createElement("p");
    handoffNotice.id = "agi-campaign-envelope-notice";
    handoffNotice.textContent = "Prepares a verifier handoff only. It cannot submit evidence or promote A23.";
    handoffButton.setAttribute("aria-describedby", handoffNotice.id);
    handoffButton.addEventListener("click", async () => {
      const originalLabel = handoffButton.textContent;
      handoffButton.disabled = true;
      handoffButton.textContent = "Preparing verifier handoff…";
      try {
        const response = await fetch("/api/agi/campaign-envelope", { cache: "no-store" });
        if (!response.ok) throw new Error(`request failed (${response.status})`);
        const envelope = await response.json();
        if (
          envelope?.authority_boundary?.can_promote_autonomous_agi !== false ||
          envelope?.evaluator_custody?.held_out_data_included !== false
        ) {
          throw new Error("unexpected campaign-envelope authority boundary");
        }
        const digest = String(envelope.envelope_digest || "campaign-envelope").slice(0, 12);
        const blob = new Blob([`${JSON.stringify(envelope, null, 2)}\n`], {
          type: "application/json",
        });
        const downloadUrl = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = downloadUrl;
        anchor.download = `obus-a23-campaign-${digest}.json`;
        document.body.append(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(downloadUrl);
        handoffNotice.textContent = "Verifier handoff downloaded. It is not a qualification receipt and cannot promote A23.";
      } catch (error) {
        handoffNotice.textContent = "Verifier handoff is unavailable. The current backend must expose its read-only campaign endpoint.";
      } finally {
        handoffButton.disabled = false;
        handoffButton.textContent = originalLabel;
      }
    });
    handoffActions.append(handoffButton, handoffNotice);
    evidenceDetails.appendChild(handoffActions);
    surface.appendChild(evidenceDetails);

    const lifecycleDetails = document.createElement("details");
    lifecycleDetails.id = "agi-improvement-governor-lifecycle-details";
    const lifecycleSummary = document.createElement("summary");
    lifecycleSummary.id = "agi-improvement-governor-lifecycle-summary";
    lifecycleSummary.textContent = "Lifecycle evidence";
    lifecycleDetails.appendChild(lifecycleSummary);
    const lifecycle = document.createElement("ol");
    lifecycle.id = "agi-improvement-governor-lifecycle";
    lifecycle.setAttribute("aria-labelledby", lifecycleSummary.id);
    lifecycleDetails.appendChild(lifecycle);
    surface.appendChild(lifecycleDetails);
  }

  function appendImprovementGovernorControls(
    surface,
    primaryButtonSource,
    refreshButtonSource
  ) {
    const controls = document.createElement("div");
    controls.id = "agi-improvement-governor-controls";

    const startButton = document.createElement("button");
    startButton.id = "agi-improvement-governor-start";
    startButton.type = "button";
    startButton.textContent = "Start one improvement loop";
    startButton.setAttribute("aria-label", "Start one bounded improvement loop");
    startButton.hidden = true;
    startButton.disabled = true;
    copyGovernorClassName(startButton, primaryButtonSource);
    controls.appendChild(startButton);

    const evidenceButton = document.createElement("button");
    evidenceButton.id = "agi-improvement-governor-evidence-run";
    evidenceButton.type = "button";
    evidenceButton.textContent = "Run 3 isolated evidence probes";
    evidenceButton.setAttribute(
      "aria-label",
      "Run three isolated evidence probes for the active improvement candidate"
    );
    evidenceButton.hidden = true;
    evidenceButton.disabled = true;
    copyGovernorClassName(evidenceButton, primaryButtonSource);
    evidenceButton.addEventListener("click", runImprovementEvidenceCandidate);
    controls.appendChild(evidenceButton);

    const refreshButton = document.createElement("button");
    refreshButton.id = "agi-improvement-governor-refresh";
    refreshButton.type = "button";
    refreshButton.textContent = "Refresh governor status";
    refreshButton.setAttribute("aria-label", "Refresh improvement governor status");
    copyGovernorClassName(refreshButton, refreshButtonSource);
    controls.appendChild(refreshButton);

    surface.appendChild(controls);
  }

  function appendImprovementGovernorOutcomes(surface, badgeSource) {
    const outcomes = document.createElement("p");
    outcomes.id = "agi-improvement-governor-outcomes";
    outcomes.setAttribute("aria-label", "Terminal fail-closed lifecycle outcomes");
    const outcomesLabel = document.createElement("strong");
    outcomesLabel.textContent = "Terminal fail-closed outcomes: ";
    outcomes.appendChild(outcomesLabel);
    ["Inconclusive", "Rejected", "Rolled back"].forEach((label, index) => {
      const badge = document.createElement("span");
      copyGovernorClassName(badge, badgeSource);
      badge.textContent = label;
      if (index) outcomes.appendChild(document.createTextNode(" "));
      outcomes.appendChild(badge);
    });
    surface.appendChild(outcomes);
  }

  function appendImprovementGovernorFacts(surface, nearbyFacts) {
    const facts = document.createElement("dl");
    facts.id = "agi-improvement-governor-facts";
    copyGovernorClassName(facts, nearbyFacts);
    appendGovernorFact(facts, "Current stage", "agi-improvement-governor-stage");
    appendGovernorFact(facts, "Highest evidence gap / objective", "agi-improvement-governor-objective");
    appendGovernorFact(facts, "Lineage / candidate digest", "agi-improvement-governor-lineage");
    appendGovernorFact(facts, "Stable checkpoint", "agi-improvement-governor-checkpoint");
    appendGovernorFact(facts, "Journal integrity", "agi-improvement-governor-journal");
    appendGovernorFact(facts, "Next action", "agi-improvement-governor-next-action");
    surface.appendChild(facts);
  }

  function ensureImprovementGovernorSurface() {
    const existing = document.getElementById("agi-improvement-governor");
    if (existing) return existing;

    const heading = Array.from(document.querySelectorAll("h1, h2, h3, h4, h5, h6")).find(
      (element) =>
        String(element.textContent || "").replace(/\s+/g, " ").trim().toLowerCase() ===
        "guarded self-improvement"
    );
    if (!heading) return null;

    const card = document.getElementById("agi-improvement-card");
    const mount = heading.parentElement;
    if (!card || !mount || !card.contains(heading)) return null;
    if (!heading.id) heading.id = "agi-improvement-heading";

    const badgeSource = card.querySelector(".badge, [class*='badge']");
    const primaryButtonSource =
      document.querySelector("button.primary, button.btn-primary, button[class*='primary']") ||
      document.getElementById("agi-baseline-run");
    const refreshButtonSource = document.getElementById("agi-claim-refresh");
    const nearbyFacts = card.querySelector("dl");

    const surface = document.createElement("section");
    surface.id = "agi-improvement-governor";
    surface.setAttribute("aria-labelledby", heading.id);
    surface.setAttribute("aria-busy", "false");

    const policy = document.createElement("p");
    policy.id = "agi-improvement-governor-policy";
    policy.textContent =
      "One bounded candidate runs three fixed, isolated evidence probes against the stable checkpoint. Promotion always waits for explicit human authorization.";
    surface.appendChild(policy);

    const active = document.createElement("p");
    active.id = "agi-improvement-governor-active";
    active.textContent = "Checking for an active loop…";
    surface.appendChild(active);

    appendImprovementGovernorFacts(surface, nearbyFacts);

    appendImprovementGovernorEvidencePanels(surface, nearbyFacts);

    appendImprovementGovernorOutcomes(surface, badgeSource);

    const authorization = document.createElement("p");
    authorization.id = "agi-improvement-governor-authorization";
    authorization.textContent = "Human authorization policy is being checked.";
    surface.appendChild(authorization);

    const announcement = document.createElement("p");
    announcement.id = "agi-improvement-governor-live";
    announcement.setAttribute("role", "status");
    announcement.setAttribute("aria-live", "polite");
    announcement.setAttribute("aria-atomic", "true");
    surface.appendChild(announcement);

    appendImprovementGovernorControls(surface, primaryButtonSource, refreshButtonSource);
    mount.appendChild(surface);
    return surface;
  }

  function setImprovementGovernorBusy(isBusy) {
    const surface = document.getElementById("agi-improvement-governor");
    const startButton = document.getElementById("agi-improvement-governor-start");
    const evidenceButton = document.getElementById("agi-improvement-governor-evidence-run");
    const refreshButton = document.getElementById("agi-improvement-governor-refresh");
    if (surface) surface.setAttribute("aria-busy", isBusy ? "true" : "false");
    if (startButton) {
      startButton.disabled = isBusy || startButton.dataset.allowed !== "true";
    }
    if (evidenceButton) {
      evidenceButton.disabled = isBusy || evidenceButton.dataset.allowed !== "true";
    }
    if (refreshButton) refreshButton.disabled = isBusy;
  }

  function announceImprovementGovernor(message) {
    setText("agi-improvement-governor-live", message);
  }

  function renderImprovementGovernorLifecycle(entries) {
    const lifecycle = document.getElementById("agi-improvement-governor-lifecycle");
    const summary = document.getElementById("agi-improvement-governor-lifecycle-summary");
    if (!lifecycle) return;
    lifecycle.replaceChildren();
    const badgeSource = document.querySelector(
      "#agi-improvement-governor-outcomes .badge, #agi-improvement-governor-outcomes [class*='badge']"
    );
    if (!Array.isArray(entries) || entries.length === 0) {
      if (summary) summary.textContent = "Lifecycle evidence · unavailable";
      const item = document.createElement("li");
      item.textContent = "Lifecycle evidence is unavailable.";
      lifecycle.appendChild(item);
      return;
    }
    if (summary) {
      const current = entries.find((entry) => entry && entry.status === "current");
      summary.textContent = current
        ? `Lifecycle evidence · ${humanizeGovernorValue(current.stage)}`
        : `Lifecycle evidence · ${entries.length} recorded step${entries.length === 1 ? "" : "s"}`;
    }
    entries.forEach((entry) => {
      const item = document.createElement("li");
      const badge = document.createElement("span");
      copyGovernorClassName(badge, badgeSource);
      const stage = entry && typeof entry === "object" ? entry.stage : entry;
      const status = entry && typeof entry === "object" ? entry.status : "recorded";
      badge.textContent = `${humanizeGovernorValue(stage)} · ${humanizeGovernorValue(status)}`;
      badge.dataset.status = String(status || "unknown");
      if (status === "current") badge.setAttribute("aria-current", "step");
      item.appendChild(badge);
      lifecycle.appendChild(item);
    });
  }

  function renderImprovementEvidence(payload, loop) {
    const screening = loop.screening && typeof loop.screening === "object" ? loop.screening : {};
    const candidateRun = payload?.candidate_run && typeof payload.candidate_run === "object"
      ? payload.candidate_run
      : {};
    const evidence = candidateRun.evidence_summary && typeof candidateRun.evidence_summary === "object"
      ? candidateRun.evidence_summary
      : screening.evidence_summary && typeof screening.evidence_summary === "object"
        ? screening.evidence_summary
        : {};
    const receiptDigest =
      candidateRun.receipt_digest || screening.receipt_digest || loop.receipt_digest;
    const attestationDigest =
      candidateRun.attestation_digest || screening.attestation_digest || loop.attestation_digest;
    const hasEvidence = Boolean(evidence.invocation_id || receiptDigest);
    const requestedContext = Number(evidence.requested_context) || 0;
    const observedContext = Number(evidence.observed_context) || 0;
    const staleQwenContext =
      hasEvidence &&
      evidence.model === "hf.co/OBLITERATUS/Qwen3.8-27B-OBLITERATED:Q4_K_M" &&
      (requestedContext > 65536 || observedContext > 65536);
    const freshStartAllowed =
      payload?.next_action === "start_new_loop" && payload?.active_loop == null;
    const selection =
      payload?.improvement_selection && typeof payload.improvement_selection === "object"
        ? payload.improvement_selection
        : null;
    const selectionBlocksStart = selection?.task_selection_permitted === false;
    const selectionMessage =
      typeof selection?.message === "string" && selection.message.trim()
        ? selection.message.trim()
        : "";
    const staleQwenContextBlocksStart = staleQwenContext && !freshStartAllowed;
    const startBlocked = selectionBlocksStart || staleQwenContextBlocksStart;
    const applyStartEligibilityBlock = () => {
      const startButton = document.getElementById("agi-improvement-governor-start");
      if (!startButton) return;
      startButton.disabled = startBlocked;
      startButton.textContent = selectionBlocksStart
        ? "Measured baseline blocks a loop"
        : staleQwenContextBlocksStart
          ? "Legacy 262k loop blocked"
          : "Start one improvement loop";
      startButton.title = selectionBlocksStart
        ? `Blocked: ${selectionMessage || "the measured baseline does not select a candidate."}`
        : staleQwenContextBlocksStart
          ? "Blocked: this legacy Qwen evidence requested more than the verified 65,536-token runtime profile."
          : "";
    };
    const legacyButton = document.getElementById("agi-improvement-governor-start");
    if (legacyButton) {
      legacyButton._obusLegacyContextObserver?.disconnect();
      delete legacyButton._obusLegacyContextObserver;
      if (startBlocked) {
        const observer = new MutationObserver(() => {
          if (!legacyButton.disabled) legacyButton.disabled = true;
        });
        observer.observe(legacyButton, { attributes: true, attributeFilter: ["disabled"] });
        legacyButton._obusLegacyContextObserver = observer;
      }
    }
    applyStartEligibilityBlock();
    queueMicrotask(applyStartEligibilityBlock);
    setText(
      "agi-improvement-governor-receipt",
      hasEvidence
        ? `${shortGovernorDigest(receiptDigest)} · attestation ${shortGovernorDigest(attestationDigest)}`
        : "Not run"
    );
    setText(
      "agi-improvement-governor-isolation",
      hasEvidence
        ? `${humanizeGovernorValue(evidence.sandbox_kind)} · image ${shortGovernorDigest(
            evidence.image_digest
          )}`
        : "Not run"
    );
    setText(
      "agi-improvement-governor-probes",
      hasEvidence
        ? `${Number(evidence.probe_passes) || 0}/${Number(evidence.probe_runs) || 3} passed · suite ${shortGovernorDigest(
            evidence.test_digest
          )}`
        : "Not run"
    );
    setText(
      "agi-improvement-governor-warm-target",
      hasEvidence
        ? `${evidence.model || "unknown model"} · requested ${requestedContext} · observed ${observedContext}${
            staleQwenContext ? " · invalid legacy context profile" : ""
          }`
        : "Not run"
    );
    setText(
      "agi-improvement-governor-evidence-summary",
      hasEvidence
        ? selectionBlocksStart
          ? `Candidate evidence · ${selectionMessage || "the measured baseline does not select a candidate"}`
          : staleQwenContext
            ? staleQwenContextBlocksStart
              ? "Candidate evidence · invalid legacy context profile; a new loop is blocked"
              : "Candidate evidence · invalid legacy context profile retained; a fresh loop is allowed by the current governor state"
            : `Candidate evidence · ${evidence.residency_verified === true ? "verified" : "not verified"}`
        : "Candidate evidence · not run"
    );
    const details = document.getElementById("agi-improvement-governor-evidence");
    if (details) details.open = hasEvidence;
  }

  function renderImprovementGovernorOperatorState(context) {
    const {
      activeLoop,
      latestLoop,
      integrityBlocked,
      policyVerified,
      canRunEvidence,
      canStart,
      stage,
      startButton,
      evidenceButton,
      refreshButton,
    } = context;
    if (activeLoop) {
      const loopLabel = shortGovernorDigest(activeLoop.loop_id);
      const activeMessage = canRunEvidence
        ? `Loop ${loopLabel} is isolated and ready for three fixed evidence probes.`
        : stage === "awaiting_authorization"
          ? `Loop ${loopLabel} passed screening and is awaiting explicit human authorization.`
          : `Loop ${loopLabel} is active at ${humanizeGovernorValue(activeLoop.stage)}.`;
      setText("agi-improvement-governor-active", activeMessage);
    } else if (integrityBlocked) {
      setText(
        "agi-improvement-governor-active",
        "New loops are blocked because journal integrity is not verified."
      );
    } else if (latestLoop) {
      setText(
        "agi-improvement-governor-active",
        `No loop is active. The latest loop ended at ${humanizeGovernorValue(latestLoop.stage)}.`
      );
    } else if (!canStart && policyVerified) {
      setText(
        "agi-improvement-governor-active",
        "No new loop is offered: the measured baseline has not selected an eligible candidate, so Obus stays idle instead of inventing work."
      );
    } else {
      setText("agi-improvement-governor-active", "No improvement loop is active.");
    }

    setText(
      "agi-improvement-governor-authorization",
      policyVerified
        ? stage === "awaiting_authorization"
          ? "Screening evidence passed. Promotion remains blocked until a human authorizes this exact candidate outside this surface."
          : "Human authorization is required. Autonomous promotion is disabled, and no authorize or promote API is exposed."
        : "Promotion policy is unavailable or inconsistent. No authorize or promote control is exposed."
    );

    if (startButton) {
      startButton.dataset.allowed = canStart ? "true" : "false";
      startButton.hidden = !canStart;
      startButton.disabled = !canStart;
    }
    if (evidenceButton) {
      evidenceButton.dataset.allowed = canRunEvidence ? "true" : "false";
      evidenceButton.dataset.loopId = activeLoop?.loop_id || "";
      evidenceButton.hidden = !canRunEvidence;
      evidenceButton.disabled = !canRunEvidence;
    }
    if (refreshButton) {
      refreshButton.hidden = false;
      refreshButton.textContent = activeLoop ? "Refresh active loop" : "Refresh governor status";
      refreshButton.setAttribute(
        "aria-label",
        activeLoop ? "Refresh the active improvement loop" : "Refresh improvement governor status"
      );
    }
  }

  function renderImprovementGovernor(payload) {
    ensureImprovementGovernorSurface();
    const activeLoop = payload?.active_loop && typeof payload.active_loop === "object"
      ? payload.active_loop
      : null;
    const latestLoop = payload?.latest_loop && typeof payload.latest_loop === "object"
      ? payload.latest_loop
      : null;
    const selectionIdle = payload?.next_action === "no_measured_local_deficit";
    const latestStage = String(latestLoop?.stage || "").toLowerCase();
    const historicalTerminal = !activeLoop && ["rolled_back", "rejected", "inconclusive"].includes(latestStage);
    const loop = activeLoop || (selectionIdle ? {} : latestLoop || {});
    const journal = payload?.journal && typeof payload.journal === "object" ? payload.journal : {};
    const lineage = loop.candidate_lineage && typeof loop.candidate_lineage === "object"
      ? loop.candidate_lineage
      : {};
    const stage = String(
      activeLoop?.stage || (selectionIdle ? "idle" : loop.stage || payload?.state || "idle")
    );
    const eventCount = Number(journal.event_count);
    const journalVerified = journal.verified === true && journal.integrity === "verified";
    const policyVerified =
      payload?.human_authorization_required === true &&
      payload?.autonomous_promotion_permitted === false &&
      payload?.promotion_authorized === false;
    const integrityBlocked = payload?.state === "integrity_error" || !journalVerified;
    const startPermittedByState = ["start_loop", "start_new_loop"].includes(payload?.next_action);
    const canStart = !activeLoop && !integrityBlocked && policyVerified && startPermittedByState;
    const canRunEvidence = Boolean(
      activeLoop && stage === "sandboxed" && !integrityBlocked && policyVerified
    );
    const startButton = document.getElementById("agi-improvement-governor-start");
    const evidenceButton = document.getElementById("agi-improvement-governor-evidence-run");
    const refreshButton = document.getElementById("agi-improvement-governor-refresh");

    setText(
      "agi-improvement-governor-stage",
      historicalTerminal
        ? `Historical · ${humanizeGovernorValue(latestStage)}`
        : humanizeGovernorValue(stage)
    );
    setText(
      "agi-improvement-governor-objective",
      historicalTerminal
        ? "No current candidate. The terminal record below is retained for audit, including any legacy context profile, but is not active."
        : selectionIdle
          ? "No current candidate selected by the measured baseline. Historical loop evidence is retained, not active."
          : formatGovernorObjective(loop.objective)
    );
    setText(
      "agi-improvement-governor-lineage",
      historicalTerminal
        ? `Historical evidence only · Parent ${shortGovernorDigest(
          lineage.parent_checkpoint_digest || loop.baseline_digest
        )} · Candidate ${shortGovernorDigest(lineage.candidate_digest)}`
        : selectionIdle
          ? "No current candidate lineage. Historical evidence remains in the verified journal."
          : `Parent ${shortGovernorDigest(
            lineage.parent_checkpoint_digest || loop.baseline_digest
          )} · Candidate ${shortGovernorDigest(lineage.candidate_digest)}`
    );
    setText(
      "agi-improvement-governor-checkpoint",
      formatGovernorCheckpoint(payload?.stable_checkpoint || loop.stable_checkpoint)
    );
    setText(
      "agi-improvement-governor-journal",
      `${journalVerified ? "Verified" : "Unverified"} · ${
        Number.isFinite(eventCount)
          ? `${eventCount} event${eventCount === 1 ? "" : "s"}`
          : "event count unavailable"
      }`
    );
    setText(
      "agi-improvement-governor-next-action",
      historicalTerminal
        ? "No active loop. Retained candidate details are historical evidence, not the active runtime target; use Default local model above for the current profile."
        : selectionIdle
          ? "No measured local deficit: local Qwen meets the current baseline, so no candidate is selected."
          : formatGovernorNextAction(payload?.next_action)
    );
    renderImprovementEvidence(payload, loop);
    renderImprovementGovernorLifecycle(selectionIdle ? null : payload?.lifecycle);

    renderImprovementGovernorOperatorState({
      activeLoop,
      latestLoop: selectionIdle ? null : latestLoop,
      integrityBlocked,
      policyVerified,
      canRunEvidence,
      canStart,
      stage,
      startButton,
      evidenceButton,
      refreshButton,
    });
  }

  function renderImprovementGovernorUnavailable() {
    ensureImprovementGovernorSurface();
    setText("agi-improvement-governor-stage", "Unavailable");
    setText("agi-improvement-governor-objective", "Objective unavailable.");
    setText("agi-improvement-governor-lineage", "Lineage unavailable.");
    setText("agi-improvement-governor-checkpoint", "Checkpoint unavailable.");
    setText("agi-improvement-governor-journal", "Unverified · event count unavailable");
    setText(
      "agi-improvement-governor-next-action",
      "Refresh status; no loop can start while governor state is unknown."
    );
    setText(
      "agi-improvement-governor-active",
      "Governor status is unavailable. Only refresh is available."
    );
    setText(
      "agi-improvement-governor-authorization",
      "No authorize or promote API or control is exposed."
    );
    renderImprovementGovernorLifecycle([]);
    const startButton = document.getElementById("agi-improvement-governor-start");
    if (startButton) {
      startButton.dataset.allowed = "false";
      startButton.hidden = true;
      startButton.disabled = true;
    }
    const evidenceButton = document.getElementById("agi-improvement-governor-evidence-run");
    if (evidenceButton) {
      evidenceButton.dataset.allowed = "false";
      evidenceButton.dataset.loopId = "";
      evidenceButton.hidden = true;
      evidenceButton.disabled = true;
    }
  }

  function renderImprovementLearningSignals(payload) {
    const anchor = document.getElementById("agi-improvement-governor-evidence");
    let details = document.getElementById("agi-improvement-governor-learning-signals");
    if (!anchor) return;
    if (!payload || typeof payload !== "object" || payload.selection_authority !== "advisory_only") {
      details?.remove();
      return;
    }
    if (!details) {
      details = document.createElement("details");
      details.id = "agi-improvement-governor-learning-signals";
      const summary = document.createElement("summary");
      summary.textContent = "Task learning signals · advisory only";
      const message = document.createElement("p");
      message.id = "agi-improvement-governor-learning-signals-summary";
      details.append(summary, message);
      anchor.insertAdjacentElement("afterend", details);
    }
    const receiptCount = Number.isFinite(Number(payload.terminal_receipt_count))
      ? Number(payload.terminal_receipt_count)
      : 0;
    const categories = Array.isArray(payload.stable_outcome_categories)
      ? payload.stable_outcome_categories.slice(0, 3)
      : [];
    const categorySummary = categories
      .map((item) => `${Number(item?.receipt_count) || 0} ${String(item?.state || "unknown")} via ${String(item?.provider || "unknown")}`)
      .join(" · ");
    const digest = String(payload.archive_digest || "").trim();
    const digestSummary = digest ? ` Archive ${digest.slice(0, 12)}….` : "";
    const reviewEligibility = payload.review_eligibility || {};
    const reviewPacket = payload.operator_review_packet || {};
    const reviewCategories = Array.isArray(reviewPacket.reviewable_failure_categories)
      ? reviewPacket.reviewable_failure_categories.slice(0, 3)
      : [];
    const reviewCategorySummary = reviewCategories
      .map((item) => `${Number(item?.receipt_count) || 0} failed via ${String(item?.provider || "unknown")} / ${String(item?.model || "default")}`)
      .join(" · ");
    const reviewSummary = reviewPacket.status === "review_requested"
      ? `Human review requested${reviewCategorySummary ? ` for ${reviewCategorySummary}.` : "."} ` +
        `${String(reviewPacket.recommended_next_step || "A human may prepare a separate bounded proposal.")} ` +
        "It cannot change routing, execute work, promote a change, or contribute to A23 evidence."
      : reviewEligibility.human_review_permitted
        ? "A repeated failure pattern is eligible for human review; it is not approved for automatic execution."
        : "No repeated failure pattern is eligible for review yet."
    setText(
      "agi-improvement-governor-learning-signals-summary",
      `${receiptCount} terminal task receipts${categorySummary ? `: ${categorySummary}.` : "."}${digestSummary} ` +
        `${reviewSummary} Signals cannot start work or change routing.`
    );
  }

  function refreshImprovementGovernorStatus(successAnnouncement) {
    if (governorRefreshPromise) return governorRefreshPromise;
    if (!ensureImprovementGovernorSurface()) return Promise.resolve(null);
    setImprovementGovernorBusy(true);
    announceImprovementGovernor("Refreshing improvement governor status…");

    const request = (async () => {
      try {
        const response = await fetch("/api/improvement/governor", {
          headers: { Accept: "application/json" },
          cache: "no-store",
        });
        const payload = await response.json().catch(() => null);
        if (!payload || typeof payload !== "object") {
          throw new Error(`Governor status failed (${response.status})`);
        }
        let sourceFreshness = {
          available: false,
          source_current: false,
          reason: "The running backend did not prove its loaded source is current.",
        };
        try {
          const freshnessResponse = await fetch("/api/runtime/source-freshness", {
            headers: { Accept: "application/json" },
            cache: "no-store",
          });
          const freshnessPayload = await freshnessResponse.json().catch(() => null);
          const sourceCurrent =
            freshnessResponse.ok &&
            freshnessPayload &&
            typeof freshnessPayload === "object" &&
            freshnessPayload.source_current === true &&
            freshnessPayload.loaded_source_mtime_ns === freshnessPayload.current_source_mtime_ns;
          sourceFreshness = {
            available: freshnessResponse.ok,
            source_current: sourceCurrent,
            reason: sourceCurrent
              ? "The running backend matches its loaded source."
              : "The running backend cannot prove it matches the current source. Restart it before new improvement work.",
          };
        } catch (_freshnessError) {
          // Missing or unreachable freshness support is deliberately treated as stale/unknown.
        }
        payload.runtime_source_freshness = sourceFreshness;
        if (!sourceFreshness.source_current) {
          payload.improvement_selection = {
            ...(payload.improvement_selection && typeof payload.improvement_selection === "object"
              ? payload.improvement_selection
              : {}),
            task_selection_permitted: false,
            message: sourceFreshness.reason,
          };
        }
        let learningSignals = null;
        try {
          const signalResponse = await fetch("/api/harness/learning-signals?limit=200", {
            headers: { Accept: "application/json" },
            cache: "no-store",
          });
          if (signalResponse.ok) {
            const signalPayload = await signalResponse.json().catch(() => null);
            if (signalPayload && typeof signalPayload === "object") learningSignals = signalPayload;
          }
        } catch (_signalError) {
          // An older backend may not expose learning signals yet; governor status remains usable.
        }
        renderImprovementGovernor(payload);
        renderImprovementLearningSignals(learningSignals);
        if (!response.ok) {
          if (response.status === 409 && payload.state === "integrity_error") {
            announceImprovementGovernor(
              "Journal integrity could not be verified. New loops remain blocked."
            );
            return payload;
          }
          throw new Error(`Governor status failed (${response.status})`);
        }
        announceImprovementGovernor(
          successAnnouncement ||
            (!sourceFreshness.source_current
              ? "Runtime source freshness cannot be verified. New improvement work remains blocked until the backend is restarted."
              : payload.active_loop
                ? "Active improvement loop status refreshed."
                : "Improvement governor status refreshed.")
        );
        return payload;
      } catch (_error) {
        renderImprovementGovernorUnavailable();
        announceImprovementGovernor(
          "Improvement governor status could not be loaded. No loop can start until refresh succeeds."
        );
        return null;
      }
    })();
    governorRefreshPromise = request;
    return request.finally(() => {
      if (governorRefreshPromise === request) governorRefreshPromise = null;
      setImprovementGovernorBusy(false);
    });
  }

  async function runImprovementEvidenceCandidate() {
    const evidenceButton = document.getElementById("agi-improvement-governor-evidence-run");
    const loopId = String(evidenceButton?.dataset.loopId || "").trim();
    if (!loopId || evidenceButton?.dataset.allowed !== "true") {
      announceImprovementGovernor(
        "No sandboxed candidate is ready. Refresh the governor before running evidence."
      );
      return null;
    }

    setImprovementGovernorBusy(true);
    announceImprovementGovernor(
      "Running three fixed probes in an isolated, network-disabled candidate environment…"
    );
    try {
      const response = await fetch(
        `/api/improvement/governor/${encodeURIComponent(loopId)}/screen`,
        {
          method: "POST",
          headers: { Accept: "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({
          candidate_kind: "ollama-warm-residency-v1",
          ...(() => {
            const isRetry = evidenceButton.dataset.candidateAttemptLoop === loopId;
            evidenceButton.dataset.candidateAttemptLoop = loopId;
            return isRetry ? { retry_key: createGovernorIdempotencyKey() } : {};
          })(),
        }),
        }
      );
      const payload = await response.json().catch(() => null);
      if (!payload || typeof payload !== "object") {
        throw new Error(`Evidence run failed (${response.status})`);
      }
      renderImprovementGovernor(payload);
      const screenedLoop = payload.active_loop || payload.latest_loop || {};
      if (!response.ok || screenedLoop.stage !== "awaiting_authorization") {
        throw new Error(payload.detail || `Evidence run failed (${response.status})`);
      }
      announceImprovementGovernor(
        "Three isolated probes passed. This exact candidate now awaits human authorization."
      );
      return payload;
    } catch (_error) {
      await refreshImprovementGovernorStatus();
      announceImprovementGovernor(
        "Evidence did not pass. Promotion remains blocked; inspect the recorded lifecycle evidence."
      );
      return null;
    } finally {
      setImprovementGovernorBusy(false);
    }
  }

  function createGovernorIdempotencyKey() {
    if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
    return `governor-loop-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function startOneImprovementLoop() {
    if (governorStartPromise) return governorStartPromise;
    const startButton = document.getElementById("agi-improvement-governor-start");
    if (!startButton || startButton.hidden || startButton.dataset.allowed !== "true") {
      announceImprovementGovernor(
        "Refresh governor status before starting a loop; only one nonterminal loop is allowed."
      );
      return Promise.resolve(null);
    }

    governorStartIdempotencyKey =
      governorStartIdempotencyKey || createGovernorIdempotencyKey();
    setImprovementGovernorBusy(true);
    announceImprovementGovernor("Starting one bounded improvement loop…");

    const request = (async () => {
      try {
        const response = await fetch("/api/improvement/governor/loops", {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
            "Idempotency-Key": governorStartIdempotencyKey,
          },
          body: JSON.stringify({}),
        });
        const payload = await response.json().catch(() => null);
        if (payload && typeof payload === "object") renderImprovementGovernor(payload);
        if (!response.ok) {
          const detail =
            payload && typeof payload.detail === "string" ? `: ${payload.detail}` : "";
          throw new Error(`Improvement loop start failed (${response.status})${detail}`);
        }
        governorStartIdempotencyKey = "";
        await refreshImprovementGovernorStatus(
          "One improvement loop started. Current evidence has been refreshed."
        );
        return payload;
      } catch (error) {
        const refreshed = await refreshImprovementGovernorStatus();
        if (refreshed?.state === "integrity_error") {
          return null;
        }
        if (refreshed?.active_loop) {
          governorStartIdempotencyKey = "";
          announceImprovementGovernor(
            "The start response failed, but an active loop exists. Only refresh is available."
          );
        } else {
          const detail = error instanceof Error ? `${error.message} ` : "";
          announceImprovementGovernor(
            `${detail}Status was refreshed; retry reuses the same request key.`
          );
        }
        return null;
      }
    })();
    governorStartPromise = request;
    return request.finally(() => {
      if (governorStartPromise === request) governorStartPromise = null;
      setImprovementGovernorBusy(false);
    });
  }

  async function refreshAgiClaimStatus() {
    setText("agi-claim-state", "Checking evidence…");
    try {
      const response = await fetch("/api/agi/status", {
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`status ${response.status}`);
      renderAgiClaim(await response.json());
    } catch (_error) {
      setText("agi-claim-state", "Status unavailable — claim not permitted");
      setText("agi-claim-verified", "Verified level: unavailable");
      setText("agi-claim-target", "Research target: unavailable");
      setText("agi-claim-attainment", "A23 attainment: not permitted");
      setText(
        "agi-claim-definition",
        "The A23 claim fails closed while its evidence policy cannot be loaded."
      );
      setText(
        "agi-claim-evidence",
        "Runtime warmth or model availability never substitutes for capability evidence."
      );
      setText("agi-claim-blockers", "Restore the local evidence service, then refresh.");
      setText("agi-improvement-policy", "Improvement promotion remains disabled.");
      setText(
        "agi-improvement-authority",
        "No candidate can self-authorize or bypass independent verification."
      );
      setText("agi-baseline-state", "Unavailable");
      setText("agi-baseline-summary", "The measured baseline service is unavailable.");
      setText("agi-baseline-gap", "Restore the local evidence service, then run again.");
      setText(
        "agi-baseline-limits",
        "No missing or failed baseline is treated as improvement or AGI evidence."
      );
    }
  }

  async function runMeasuredBaseline() {
    const button = document.getElementById("agi-baseline-run");
    if (button) button.disabled = true;
    setText("agi-baseline-state", "Running 36 requests…");
    setText(
      "agi-baseline-gap",
      "Comparing the same six synthetic probes across local Qwen and OmniRoute Mimo free."
    );
    try {
      const response = await fetch("/api/agi/baseline/run", {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ repeats: 3 }),
      });
      if (!response.ok) throw new Error(`status ${response.status}`);
      const report = await response.json();
      await refreshAgiClaimStatus();
      const recovery = report?.runtime_recovery;
      if (recovery?.status === "restored") {
        const model = typeof recovery.model === "string" ? recovery.model : "configured local model";
        const context = Number(recovery.observed_context_tokens) || 0;
        setText(
          "agi-baseline-gap",
          `Comparison complete; configured local runtime restored: ${model}${context ? ` · ${context.toLocaleString()} context` : ""}.`
        );
        setText(
          "agi-baseline-limits",
          "Runtime recovery is operational only; this descriptive comparison cannot promote A23."
        );
      } else if (recovery) {
        setText("agi-baseline-gap", "Comparison completed, but configured local runtime recovery was not verified.");
        setText(
          "agi-baseline-limits",
          "Operational recovery needs attention. This descriptive comparison cannot promote A23."
        );
      }
    } catch (_error) {
      setText("agi-baseline-state", "Run failed");
      setText(
        "agi-baseline-gap",
        "One or more model adapters did not return a complete receipted comparison."
      );
      setText(
        "agi-baseline-limits",
        "Failure remains visible and never counts as improvement or AGI evidence."
      );
    } finally {
      if (button) button.disabled = false;
    }
  }

  function initializeAgiClaim() {
    ensureImprovementGovernorSurface();
    const refreshButton = document.getElementById("agi-claim-refresh");
    const baselineButton = document.getElementById("agi-baseline-run");
    const governorStartButton = document.getElementById("agi-improvement-governor-start");
    const governorRefreshButton = document.getElementById("agi-improvement-governor-refresh");
    if (refreshButton) {
      refreshButton.addEventListener("click", () => {
        refreshAgiClaimStatus();
        refreshEpistemicPolicyStatus();
      });
    }
    if (baselineButton) baselineButton.addEventListener("click", runMeasuredBaseline);
    if (governorStartButton) governorStartButton.addEventListener("click", startOneImprovementLoop);
    if (governorRefreshButton) {
      governorRefreshButton.addEventListener("click", () => refreshImprovementGovernorStatus());
    }
    refreshAgiClaimStatus();
    refreshEpistemicPolicyStatus();
    refreshImprovementGovernorStatus();
  }

  window.refreshAgiClaimStatus = refreshAgiClaimStatus;
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeAgiClaim, { once: true });
  } else {
    initializeAgiClaim();
  }
})();
