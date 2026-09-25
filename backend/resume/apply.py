"""Build the tailored resume from the MASTER profile + reviewed session.

Port of jobMatchPanel.buildTailoredProfile, moved server-side so the
backend decides what reaches the final file:
  * only ``accepted`` / ``edited`` changes are applied (edited text wins);
  * a change is applied only if its ``original`` still equals the master
    line (otherwise it is skipped and reported);
  * every applied text is re-validated against the master profile: an
    accepted change that fails evidence validation is skipped (so neither a
    stale/tampered session nor "Accept All Safe" can ship it); a failing
    user edit is applied only if the user explicitly overrode the warning
    (``userFlagged``) and is reported as an override;
  * the master profile is deep-copied, never mutated;
  * protected facts are asserted unchanged.
"""

from __future__ import annotations

import copy

from ..models.candidate import protected_facts
from .validator import validate_changes

APPLIED = ("accepted", "edited")


class ProtectedFactError(RuntimeError):
    pass


def displayed_text(change: dict) -> str:
    return change["editedText"] if change.get("editedText") is not None else change.get("updated", "")


def build_tailored_profile(master: dict, session: dict | None) -> tuple[dict, list[str], list[str], list[str]]:
    """Returns (tailored_profile, applied_change_ids, skipped_messages, override_change_ids)."""
    tailored = copy.deepcopy(master)
    applied: list[str] = []
    skipped: list[str] = []
    overrides: list[str] = []
    changes = (session or {}).get("changes") or []
    jd_keywords = [k.get("keyword") for k in (session or {}).get("keywords") or [] if isinstance(k, dict) and k.get("keyword")]
    job_title = (session or {}).get("jobTitle") or ""

    def change_for(bullet_id: str):
        return next((c for c in changes if c.get("targetBulletId") == bullet_id), None)

    def apply(bullet_id: str, current: str) -> str:
        change = change_for(bullet_id)
        if not change or change.get("status") not in APPLIED:
            return current
        if (change.get("original") or "").strip() != (current or "").strip():
            skipped.append(f"Change {change.get('id')} skipped: the original line changed since tailoring.")
            return current
        text = displayed_text(change).strip()
        if not text:
            skipped.append(f"Change {change.get('id')} skipped: empty text.")
            return current
        check = validate_changes([{**change, "updated": text}], master, jd_keywords=jd_keywords, job_title=job_title)
        if check.blocked:
            reasons = " ".join(check.blocked[0]["reasons"])
            if change.get("status") == "edited" and change.get("userFlagged"):
                overrides.append(change.get("id"))   # explicit user override of a flagged edit
            else:
                skipped.append(f"Change {change.get('id')} skipped: failed evidence validation ({reasons})")
                return current
        applied.append(change.get("id"))
        return text

    summary = tailored.setdefault("summary", {"text": ""})
    summary["text"] = apply("summary", summary.get("text", ""))
    for exp in tailored.get("experience") or []:
        for bullet in exp.get("bullets") or []:
            bullet["text"] = apply(bullet.get("id"), bullet.get("text", ""))

    if protected_facts(tailored) != protected_facts(master):
        raise ProtectedFactError("Protected facts changed while building the tailored resume.")
    return tailored, applied, skipped, overrides
