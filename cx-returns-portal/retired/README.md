# Retired: the direct ShipStation path

Superseded on 2026-08-28. Replacements now go into the **Replacements** tab of the
replacements sheet, and an automation that already existed creates the ShipStation
order from there. This skill no longer connects to ShipStation.

Kept rather than deleted because the research in it is real and was expensive to
get, and because some of it stays true:

| File | Still worth reading for |
|---|---|
| `shipstation-access-request.md` | What a Claude Code environment can and cannot do about egress and credentials — including that per-host credential injection is not user-configurable |
| `cloud-reship-runbook.md` | The environment-settings mechanics, and that network policy applies immediately while environment variables only reach sessions started afterwards |
| `shipstation-csv.{md,json}` | The CSV import column map, if a bulk import is ever needed |
| `shipstation-discovered.json` | Store IDs, since confirmed by the sheet's own config tab |
| `create_reship_order.py`, `shipstation_probe.py` | A worked example of gating a write that has physical consequences |
| `MOVE-TO-OWN-REPO.md` | Stale: that move is decided, and this content now belongs wherever the skill lands |

**None of this is wired up.** Nothing in `SKILL.md` or the portal refers to it.
`scripts/confirm_940.py` was *not* retired — it still verifies that a replacement
reached the warehouse as an EDI 940, which matters more now that the order is
created by something this skill cannot see.
