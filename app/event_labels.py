"""Per-feed display titles for the v2 hero and radar (``CAL_<KEY>_*_LABEL``).

A feed may set a closed label (holiday-category events) and a dismissal label
(early-dismissal events); a matching event then reads "<label> – <cleaned
title>" on the hero lines and the radar. Grid chips keep the raw title.
"""

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from typing import Any

from app.config import CALENDAR_FEEDS, HERO_HOLIDAY_CATEGORIES
from app.event_styles import EVENT_CATEGORIES

#: The event_styles category whose keywords mark an early dismissal.
DISMISSAL_CATEGORY = "school"

#: A "/" (any spacing) or a spaced hyphen / en dash — never a hyphenated word.
_SEP = r"(?:\s*/\s*|\s+[-–]\s+)"


def labelled(title: str, label: str) -> str:
    """ "<label> – <title>", the title cut at its first ':' and with any
    "/"- or " - "-separated part naming the label dropped (case-insensitive),
    together with its separator: "End of Quarter/Early Dismissal for students"
    -> "Early dismissal – End of Quarter"."""
    pieces = re.split(f"({_SEP})", title.split(":", 1)[0])
    kept: list[str] = []
    for i in range(0, len(pieces), 2):
        part = pieces[i]
        if not part.strip() or label.lower() in part.lower():
            continue
        if kept:  # the separator that preceded this part
            kept.append(pieces[i - 1])
        kept.append(part)
    text = "".join(kept).strip()
    return f"{label} – {text}" if text else label


def _category_matches(key: str, title: str) -> bool:
    # Any match, not just the winning category: "End of Quarter/Early
    # Dismissal" is drawn as `quarter` but is still an early dismissal.
    return any(c.key == key and c.matches(title) for c in EVENT_CATEGORIES)


@dataclass(frozen=True)
class TitleLabels:
    """Feed key -> label for each rule, plus what makes an event match it."""

    closed: Mapping[str, str] = field(default_factory=dict)
    dismissal: Mapping[str, str] = field(default_factory=dict)
    holiday_categories: Collection[str] = HERO_HOLIDAY_CATEGORIES
    dismissal_category: str = DISMISSAL_CATEGORY

    def title(self, event: dict[str, Any]) -> str:
        """The display title for ``event``; closed beats dismissal."""
        source, title = event["source"], event["title"]
        closed = self.closed.get(source)
        if closed and event["category"] in self.holiday_categories:
            return labelled(title, closed)
        dismissal = self.dismissal.get(source)
        if dismissal and _category_matches(self.dismissal_category, title):
            return labelled(title, dismissal)
        return title


#: The labels configured in ``.env``.
FEED_LABELS = TitleLabels(
    closed={f.key: f.closed_label for f in CALENDAR_FEEDS if f.closed_label},
    dismissal={f.key: f.dismissal_label for f in CALENDAR_FEEDS if f.dismissal_label},
)

#: No labels at all — raw titles everywhere.
NO_LABELS = TitleLabels()
