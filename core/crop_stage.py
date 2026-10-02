"""
Crop-stage calculator for wheat (deterministic, no AI).

Days-after-sowing (DAS) ranges are approximate values for TIMELY sown
irrigated wheat in the North-Western Plains Zone. Late-sown crops develop
faster in warmer weather, so the app shows a caveat for them (see
docs: this is a known limitation that we deliberately surface).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Stage:
    key: str
    name: str
    name_hi: str
    start: int  # first DAS of the stage (inclusive)
    end: int    # last DAS of the stage (inclusive)


STAGES: list[Stage] = [
    Stage("germination", "Germination", "अंकुरण", 0, 7),
    Stage("seedling", "Seedling", "पौध अवस्था", 8, 19),
    Stage("cri", "Crown root initiation", "शिखर जड़ (CRI)", 20, 30),
    Stage("tillering", "Tillering", "कल्ले निकलना", 31, 50),
    Stage("jointing", "Jointing", "गांठ बनना", 51, 70),
    Stage("booting", "Booting", "गोभ अवस्था", 71, 80),
    Stage("heading", "Heading & flowering", "बाली व फूल", 81, 100),
    Stage("milk", "Milk stage", "दूधिया दाना", 101, 115),
    Stage("dough", "Dough stage", "दाना सख्त होना", 116, 130),
    Stage("maturity", "Maturity & harvest", "पकाई व कटाई", 131, 165),
]
PRE_SOWING = Stage("pre_sowing", "Pre-sowing", "बुवाई से पहले", -9999, -1)
SEASON_END = STAGES[-1].end

# Critical irrigations (approximate DAS) from KB-08
CRITICAL_IRRIGATIONS = [
    (22, "Crown root initiation (most critical)"),
    (42, "Tillering"),
    (63, "Jointing"),
    (83, "Flowering"),
    (103, "Milk stage"),
    (118, "Dough stage"),
]

WEED_WINDOW = (30, 35)  # KB-09


def sowing_window(sowing: date) -> str:
    """Classify the sowing date for the NW plains (KB-01)."""
    # season year = the year the crop is sown in (Oct-Dec) or the previous year (Jan)
    y = sowing.year if sowing.month >= 7 else sowing.year - 1
    if sowing < date(y, 10, 25):
        return "early"
    if sowing <= date(y, 11, 20):
        return "timely"
    if sowing <= date(y, 12, 20):
        return "late"
    return "very_late"


def estimate(sowing: date | None, on: date) -> dict:
    """Return the crop situation on date `on` for a crop sown on `sowing`.

    status:
      not_sown      no sowing date given, or sowing date is after `on`
      growing       inside the modelled season
      beyond        more than SEASON_END days after sowing (probably harvested / wrong date)
    """
    result = {
        "status": "not_sown",
        "das": None,
        "stage": PRE_SOWING,
        "next_stage": STAGES[0],
        "days_to_next": None,
        "progress": 0.0,
        "window": None,
        "warnings": [],
        "next_irrigation": None,
        "in_weed_window": False,
    }
    if sowing is None:
        return result

    result["window"] = sowing_window(sowing)
    das = (on - sowing).days

    if das < 0:
        result["warnings"].append(
            f"The sowing date is {-das} day(s) after the advisory date, so the crop is treated as not sown yet."
        )
        return result

    result["das"] = das
    if das > SEASON_END:
        result["status"] = "beyond"
        result["stage"] = STAGES[-1]
        result["next_stage"] = None
        result["progress"] = 1.0
        result["warnings"].append(
            f"It is {das} days since sowing, longer than a normal wheat season (~{SEASON_END} days). "
            "Please check the sowing date."
        )
        return result

    result["status"] = "growing"
    for i, st in enumerate(STAGES):
        if st.start <= das <= st.end:
            result["stage"] = st
            nxt = STAGES[i + 1] if i + 1 < len(STAGES) else None
            result["next_stage"] = nxt
            result["days_to_next"] = (nxt.start - das) if nxt else None
            break
    result["progress"] = round(das / SEASON_END, 4)
    result["in_weed_window"] = WEED_WINDOW[0] - 3 <= das <= WEED_WINDOW[1] + 3

    for irr_das, label in CRITICAL_IRRIGATIONS:
        if irr_das >= das - 2:
            result["next_irrigation"] = {"das": irr_das, "label": label, "in_days": max(irr_das - das, 0)}
            break

    if result["window"] in ("late", "very_late"):
        result["warnings"].append(
            "Late-sown crop: stages are estimated for timely sowing; late-sown wheat develops faster in warm "
            "weather, so confirm the stage by looking at the plants."
        )
    if result["window"] == "early":
        result["warnings"].append(
            "Sown before 25 October: early sowing in warm weather can reduce tillering."
        )
    return result


def stage_by_key(key: str) -> Stage:
    if key == PRE_SOWING.key:
        return PRE_SOWING
    for st in STAGES:
        if st.key == key:
            return st
    raise KeyError(key)
