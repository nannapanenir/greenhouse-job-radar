"""Build the tailored resume from the MASTER profile + reviewed session.

Port of jobMatchPanel.buildTailoredProfile, moved server-side so the
backend decides what reaches the final file:
  * only ``accepted`` / ``edited`` changes are applied (edited text wins);
  * a change is applied only if its ``original`` still equals the master
    line (otherwise it is skipped and reported);
  * the master profile is deep-copied, never mutated;
  * protected facts are asserted unchanged.
"""

from __future__ import annotations

import copy

from ..models.candidate import protected_facts

APPLIED = ("accepted", "edited")


class ProtectedFactError(RuntimeError):
    pass


def displayed_text(change: dict) -> str:
    return change["editedText"] if change.get("editedText") is not None else change.get("updated", "")


def build_tailored_profile(master: dict, session: dict | None) -> tuple[dict, list[str], list[str]]:
    """Returns (tailored_profile, applied_change_ids, skipped_messages)."""
    tailored = copy.deepcopy(master)
    applied: list[str] = []
    skipped: list[str] = []
    changes = (session or {}).get("changes") or []

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
        applied.append(change.get("id"))
        return text

    summary = tailored.setdefault("summary", {"text": ""})
    summary["text"] = apply("summary", summary.get("text", ""))
    for exp in tailored.get("experience") or []:
        for bullet in exp.get("bullets") or []:
            bullet["text"] = apply(bullet.get("id"), bullet.get("text", ""))

    if protected_facts(tailored) != protected_facts(master):
        raise ProtectedFactError("Protected facts changed while building the tailored resume.")
    return tailored, applied, skipped
