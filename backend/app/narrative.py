"""LLM-generated narrative summary, grounded strictly in the deterministic report.

This is the only module in the app that calls an LLM. It never computes a
number itself — it receives the report dict produced by reconciliation.py and
analytics.py, asks Claude to narrate it, then verifies every numeric figure
in the response traces back to a value actually present in that report
before returning anything to the caller.
"""

import json
import re
from dataclasses import dataclass, field

import anthropic

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a clinic billing assistant. Write a short, WhatsApp-style \
end-of-day summary for a clinic owner, based ONLY on the JSON report given in the \
user message.

Rules — follow these exactly:
1. Never invent, estimate, or approximate a number. Every figure you state must be \
copied from the report, either as-is or converted from paise to rupees by dividing \
by 100 (100 paise = ₹1).
2. Do not compute derived statistics that are not already present in the report — \
no percentages, growth rates, averages, or ratios you calculate yourself. If a \
metric would be useful but the report has no data for it (for example, profit — \
there is no cost data), say plainly that it cannot be computed from the available \
data. Do not guess or approximate it.
3. Write money amounts in Indian Rupees (₹), converting from paise.
4. Keep it short: a few short sentences or bullet points, the way an owner would \
actually want to read it on WhatsApp. No headers, no markdown tables.
5. If there were zero visits, say so plainly instead of fabricating activity.
"""


@dataclass
class NarrativeResult:
    narrative: str | None
    traced_figures: dict[str, str] = field(default_factory=dict)
    error: str | None = None


def flatten_report(report: dict) -> list[tuple[str, float]]:
    """Flatten a report dict into (dotted-path, numeric value) leaves."""
    leaves: list[tuple[str, float]] = []

    def walk(node, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else key)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")
        elif isinstance(node, bool):
            return
        elif isinstance(node, (int, float)):
            leaves.append((path, float(node)))

    walk(report, "")
    return leaves


def build_traceable_candidates(report: dict) -> list[tuple[float, str]]:
    """Every value a narrative number is allowed to match, with its source path.

    Paise fields also yield their rupee equivalent (exact and rounded), since
    the narrative is expected to present money in rupees, not paise.
    """
    candidates: list[tuple[float, str]] = []
    for path, value in flatten_report(report):
        if path.endswith("_paise"):
            candidates.append((value, f"{path} (paise)"))
            rupees = value / 100
            candidates.append((round(rupees, 2), f"{path} (₹)"))
            candidates.append((round(rupees), f"{path} (₹, rounded)"))
        else:
            candidates.append((value, path))
    return candidates


_LIST_MARKER_RE = re.compile(r"(?m)^\s*\d+[.)]\s+")
_NUMBER_RE = re.compile(r"[₹$]?\s*-?\d[\d,]*(?:\.\d+)?%?")


def extract_numbers(text: str) -> list[str]:
    """Pull every number-looking token out of narrative text.

    Markdown ordinal list markers ("1. ", "2) ") are stripped first so list
    numbering is never treated as a claimed figure.
    """
    stripped = _LIST_MARKER_RE.sub("", text)
    return [match.strip() for match in _NUMBER_RE.findall(stripped)]


def _normalize(raw: str) -> tuple[float, bool] | None:
    token = raw.strip()
    is_percent = token.endswith("%")
    token = token.rstrip("%").replace("₹", "").replace("$", "").replace(",", "").strip()
    if not token or token in {"-", "."}:
        return None
    try:
        return float(token), is_percent
    except ValueError:
        return None


_MATCH_TOLERANCE = 0.01  # float-precision slack only; rounding is handled by
# the explicit "rounded" candidate variants in build_traceable_candidates,
# not by widening this tolerance — a wide tolerance would let fabricated
# numbers that happen to land near a real one slip through as "traced".


def _find_match(value: float, candidates: list[tuple[float, str]]) -> str | None:
    for candidate_value, path in candidates:
        if abs(value - candidate_value) <= _MATCH_TOLERANCE:
            return path
    return None


def validate_traceability(
    text: str, report: dict
) -> tuple[dict[str, str], list[str]]:
    """Verify every numeric figure in `text` traces back to `report`.

    Returns (traced_figures, untraced_numbers). Percentages are always
    rejected as untraceable — the report never contains a percentage field,
    so any percentage in the narrative is necessarily a computed/invented one.
    """
    candidates = build_traceable_candidates(report)
    traced: dict[str, str] = {}
    untraced: list[str] = []

    for raw in extract_numbers(text):
        parsed = _normalize(raw)
        if parsed is None:
            continue
        value, is_percent = parsed
        if is_percent:
            untraced.append(raw.strip())
            continue
        match = _find_match(value, candidates)
        if match:
            traced[raw.strip()] = match
        else:
            untraced.append(raw.strip())

    return traced, untraced


def _extract_text(response) -> str:
    blocks = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    return "\n".join(blocks).strip()


def generate_narrative(report: dict) -> NarrativeResult:
    """Generate a grounded narrative for `report`, or a clear error/fallback.

    Never raises: any LLM failure, malformed response, or untraceable number
    is returned as `NarrativeResult.error` instead of propagating.
    """
    try:
        client = anthropic.Anthropic()
    except Exception as exc:  # missing/invalid credentials, etc.
        return NarrativeResult(None, {}, f"Could not initialize the Anthropic client: {exc}")

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=700,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(report)}],
        )
    except anthropic.APIError as exc:
        return NarrativeResult(None, {}, f"LLM request failed: {exc}")
    except Exception as exc:
        return NarrativeResult(None, {}, f"Unexpected error calling the LLM: {exc}")

    if response.stop_reason == "refusal":
        return NarrativeResult(None, {}, "The model declined to generate a narrative for this report.")

    text = _extract_text(response)
    if not text:
        return NarrativeResult(None, {}, "The model returned an empty or malformed response.")

    traced, untraced = validate_traceability(text, report)
    if untraced:
        figures = ", ".join(sorted(set(untraced)))
        return NarrativeResult(
            None,
            traced,
            f"Narrative rejected: it contains figures that don't trace back to the report ({figures}).",
        )

    return NarrativeResult(text, traced, None)
