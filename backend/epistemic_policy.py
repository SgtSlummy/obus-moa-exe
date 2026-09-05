"""Versioned epistemic-honesty policy for local model calls.

The policy improves evidence handling without granting broader authority or changing
Obus's Autonomous AGI claim. Operators can roll it back explicitly through an
environment switch while invalid switch values keep the safer policy enabled.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

POLICY_ID: Final = "obus-epistemic-honesty"
POLICY_VERSION: Final = "1.1.0"
POLICY_ENV_VAR: Final = "OBUS_EPISTEMIC_POLICY"
POLICY_RECEIPT: Final = "data/epistemic-calibration-policy.json"
POLICY_MARKER: Final = f"[{POLICY_ID}@{POLICY_VERSION}]"
PRIVATE_STATE_CATEGORY: Final = "unreported-private-state"
PRIVATE_STATE_RESPONSE: Final = (
    "I can't determine an unreported private state from the information available. "
    "Share the relevant information if you want me to work with it."
)

EPISTEMIC_POLICY_DIRECTIVE: Final = (
    f"{POLICY_MARKER} Before answering, silently determine whether the available "
    "evidence uniquely determines the requested answer. Never claim to know another "
    "person's unreported thoughts or private state, or current machine, workspace, "
    "account, or installed-software state, unless the user supplied it or a tool "
    "result verified it. If an answer depends on a future, hidden, private, random, "
    "missing, ambiguous, or impossible-premise fact, do not guess or select a merely "
    "plausible answer: say the evidence is insufficient and, when useful, ask for or "
    "gather the missing fact. Treat multiple plausible interpretations as ambiguous. "
    "For creative, analytical, coding, and planning work, proceed with clearly stated "
    "reasonable assumptions when exact external facts are not required. Otherwise "
    "answer directly."
)

_DISABLE_VALUES: Final = frozenset({"0", "false", "off", "disabled"})
_REQUEST_RE: Final = re.compile(
    r"\b(?:what|which|who|where|name|identify|tell me|return|provide|give me|state|"
    r"answer|predict|read|reveal|determine|correct answer|exact answer)\b"
)
_PERSON_RE: Final = re.compile(
    r"\b(?:i|me|my|mine|you|your|yours|he|him|his|she|her|hers|they|them|their|theirs)\b"
)
_PRIVATE_RE: Final = re.compile(
    r"\b(?:private|privately|secret|secretly|silent|silently|unreported|unspoken|"
    r"undisclosed|hidden)\b|\b(?:keep|kept|keeping)\b.{0,28}\b(?:to myself|to yourself|"
    r"to himself|to herself|to themselves)\b|\b(?:will not|won't|did not|didn't|never)\b"
    r".{0,20}\b(?:say|tell|share|reveal)\b|\bwithout\b.{0,20}\b(?:saying|telling|sharing|"
    r"revealing)\b|\b(?:have|has|had)\b.{0,20}\bin mind\b|\b(?:do|does|did)\b.{0,20}"
    r"\bhave in mind\b|\bthinking\b|\bread\b.{0,20}\bmind\b"
)
_PRIVATE_TARGET_RE: Final = re.compile(
    r"\b(?:answer|artist|belief|choice|city|color|decision|desire|feeling|idea|intent|"
    r"intention|name|number|opinion|preference|selection|song|state|thought|title|word|"
    r"thinking|mind)\b"
)
_CREATIVE_GUESS_RE: Final = re.compile(
    r"\b(?:make up|invent|role[- ]?play|fictional|hypothetical|pretend|random(?:ly)? guess|"
    r"guess for fun|just guess)\b"
)
_HOW_REQUEST_RE: Final = re.compile(r"\bhow\b|\b(?:advice|ways to|help me)\b")
_TECHNICAL_TOPIC_RE: Final = re.compile(
    r"\bdecision tree\b|\bprivate (?:api|channel|class|endpoint|field|function|ip|key|"
    r"member|method|network|property|repo|repository|state variable|subnet)\b"
)
_SUPPLIED_VALUE_RE: Final = re.compile(
    r"\b(?:i|you|he|she|they)\s+(?:already\s+)?(?:privately\s+|secretly\s+)?"
    r"(?:chose|selected|picked|decided on|am thinking of|are thinking of|is thinking of|"
    r"have in mind|has in mind)\s+(?!a\b|an\b|the\b|one\b|something\b|anything\b|"
    r"answer\b|choice\b|decision\b|number\b|song\b|word\b|city\b|color\b|option\b|"
    r"before\b|earlier\b|privately\b|secretly\b|silently\b|but\b|without\b|not\b)"
    r"(?:[\"'][^\"']+[\"']|[a-z0-9][a-z0-9_-]*(?:\s+[a-z0-9][a-z0-9_-]*){0,5})"
    r"(?:[.,;!?]|$)|\b(?:answer|choice|selection|city|number|word|song|decision)\s+"
    r"(?:is|was)\s+(?:[\"'][^\"']+[\"']|[a-z0-9][a-z0-9_-]*(?:\s+[a-z0-9]"
    r"[a-z0-9_-]*){0,5})(?:[.,;!?]|$)"
)


@dataclass(frozen=True, slots=True)
class EpistemicGuardDecision:
    """Deterministic pre-generation decision with non-sensitive observability fields."""

    blocked: bool
    category: str | None = None
    response: str | None = None
    reason: str = "no-guarded-pattern"
    policy_id: str = POLICY_ID
    policy_version: str = POLICY_VERSION

    def metadata(self) -> dict[str, object]:
        """Return safe event/metric metadata without echoing the user prompt."""

        return {
            "blocked": self.blocked,
            "category": self.category,
            "reason": self.reason,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
        }


def epistemic_policy_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Return whether enforcement is enabled; malformed values fail toward enforcement."""

    source = os.environ if environ is None else environ
    value = str(source.get(POLICY_ENV_VAR, "enforce")).strip().lower()
    return value not in _DISABLE_VALUES


def epistemic_policy(environ: Mapping[str, str] | None = None) -> str:
    """Return the active system directive, or an empty string after explicit rollback."""

    if not epistemic_policy_enabled(environ):
        return ""
    return EPISTEMIC_POLICY_DIRECTIVE


_UNOBSERVED_RANDOM_OUTCOME_CATEGORY = "unobserved-random-outcome"
_UNOBSERVED_RANDOM_OUTCOME_RESPONSE = "INSUFFICIENT_EVIDENCE"
_UNOBSERVED_RANDOM_EVENT_RE = re.compile(
    r"\b(?:sealed\s+)?(?:fair\s+)?(?:coin\s+(?:was\s+)?flipped|die\s+(?:was\s+)?rolled|card\s+(?:was\s+)?drawn)\b"
)
_UNOBSERVED_EVIDENCE_RE = re.compile(
    r"\b(?:no|without)\s+(?:\w+\s+){0,2}(?:observation|evidence|result|outcome)\b|\bunobserved\b"
)
_ACTUAL_OUTCOME_REQUEST_RE = re.compile(
    r"\b(?:state|report|tell|give|identify)\s+(?:me\s+)?(?:the\s+)?(?:actual\s+)?(?:outcome|side|result)\b"
    r"|\b(?:what|which)\s+(?:was|is)\s+(?:the\s+)?(?:actual\s+)?(?:outcome|side|result)\b"
)


def guard_epistemic_request(
    prompt: str,
    environ: Mapping[str, str] | None = None,
) -> EpistemicGuardDecision:
    """Block explicit attempts to infer a person's unreported private state.

    This is intentionally a narrow, auditable request gate rather than a general
    truth detector. It does not inspect or retain the private value being requested.
    """

    if not epistemic_policy_enabled(environ):
        return EpistemicGuardDecision(blocked=False, reason="operator-disabled")

    normalized = re.sub(r"\s+", " ", str(prompt)).strip().lower()
    if not normalized:
        return EpistemicGuardDecision(blocked=False, reason="empty-prompt")
    if _CREATIVE_GUESS_RE.search(normalized):
        return EpistemicGuardDecision(blocked=False, reason="explicit-creative-guess")
    if _TECHNICAL_TOPIC_RE.search(normalized):
        return EpistemicGuardDecision(blocked=False, reason="technical-topic")
    if _HOW_REQUEST_RE.search(normalized):
        return EpistemicGuardDecision(blocked=False, reason="process-or-advice-request")
    if _SUPPLIED_VALUE_RE.search(normalized):
        return EpistemicGuardDecision(blocked=False, reason="value-supplied-in-prompt")

    private_state_request = bool(
        _REQUEST_RE.search(normalized)
        and _PERSON_RE.search(normalized)
        and _PRIVATE_RE.search(normalized)
        and _PRIVATE_TARGET_RE.search(normalized)
    )
    if private_state_request:
        return EpistemicGuardDecision(
            blocked=True,
            category=PRIVATE_STATE_CATEGORY,
            response=PRIVATE_STATE_RESPONSE,
            reason="explicit-unreported-private-state-request",
        )

    unobserved_random_outcome = bool(
        _UNOBSERVED_RANDOM_EVENT_RE.search(normalized)
        and _UNOBSERVED_EVIDENCE_RE.search(normalized)
        and _ACTUAL_OUTCOME_REQUEST_RE.search(normalized)
    )
    if unobserved_random_outcome:
        return EpistemicGuardDecision(
            blocked=True,
            category=_UNOBSERVED_RANDOM_OUTCOME_CATEGORY,
            response=_UNOBSERVED_RANDOM_OUTCOME_RESPONSE,
            reason="explicit-unobserved-random-outcome-request",
        )
    return EpistemicGuardDecision(blocked=False)


def epistemic_policy_status_payload(
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Expose deterministic policy identity, rollback, and claim-boundary metadata."""

    enabled = epistemic_policy_enabled(environ)
    digest = hashlib.sha256(EPISTEMIC_POLICY_DIRECTIVE.encode("utf-8")).hexdigest()
    return {
        "policy_id": POLICY_ID,
        "version": POLICY_VERSION,
        "status": "active" if enabled else "operator-disabled",
        "enabled": enabled,
        "directive_sha256": digest,
        "evidence_receipt": POLICY_RECEIPT,
        "deterministic_guard": {
            "status": "active" if enabled else "operator-disabled",
            "mode": "pre-generation-request-gate",
            "delivery": "deterministic request gate; no universal model-prompt injection",
            "categories": [
                PRIVATE_STATE_CATEGORY,
                _UNOBSERVED_RANDOM_OUTCOME_CATEGORY,
            ],
            "response_policy": "fixed-safe-abstention",
        },
        "rollback": {
            "environment_variable": POLICY_ENV_VAR,
            "disable_values": sorted(_DISABLE_VALUES),
        },
        "claim_scope": "Epistemic behavior only; this is not evidence of AGI.",
        "known_limitation": (
            "The deterministic guard covers only explicit unreported private-state and "
            "unobserved random-outcome requests; it does not prove general factuality or "
            "current-state correctness."
        ),
        "autonomous_promotion_permitted": False,
        "autonomous_agi_promotion_permitted": False,
        "human_authorization_required_for_future_changes": True,
    }
