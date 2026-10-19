"""Hero, radar and waste blocks on /api/events (app/events_derived.py)."""

from datetime import date, datetime, timezone

from app.config import Person
from app.events_derived import closed_title, hero, radar, waste

PRISHA = Person("prisha", "Prisha", "#19b2d8", 1, ("school",), ("prisha",))
PRAPTI = Person("prapti", "Prapti", "#bc39bd", 2, (), ("prapti",))
ROSTER = (PRISHA, PRAPTI)

TODAY = date(2026, 10, 21)  # a Wednesday
NOW = datetime(2026, 10, 21, 16, 0, tzinfo=timezone.utc)  # noon local


def day(
    start: str,
    title: str,
    source: str = "family",
    end: str | None = None,
    persons: list[str] | None = None,
    category: str | None = None,
) -> dict:
    return {
        "source": source, "title": title, "start_date": start,
        "end_date": end or start, "all_day": True,
        "start_utc": f"{start}T04:00:00+00:00", "end_utc": None,
        "category": category, "persons": persons or [],
    }


def timed(start_utc: str, end_utc: str, title: str, persons: list[str]) -> dict:
    return {
        "source": "family", "title": title, "start_date": start_utc[:10],
        "end_date": end_utc[:10], "all_day": False, "start_utc": start_utc,
        "end_utc": end_utc, "category": None, "persons": persons,
    }


def run_hero(events: list[dict]) -> dict:
    return hero(events, TODAY, NOW, ROSTER, {"family"}, {"holiday"}, {})


# --- hero --------------------------------------------------------------------


def test_next_skips_past_events_per_person() -> None:
    events = [
        day("2026-10-20", "Yesterday", "school", persons=["prisha"]),
        timed("2026-10-21T13:00:00+00:00", "2026-10-21T14:00:00+00:00",
              "Ended this morning", ["prisha"]),
        timed("2026-10-21T15:00:00+00:00", "2026-10-21T17:00:00+00:00",
              "Prisha in progress", ["prisha"]),
        day("2026-10-23", "Prapti daycare photos", persons=["prapti"]),
    ]
    cols = run_hero(events)["persons"]
    assert [c["key"] for c in cols] == ["prisha", "prapti"]
    assert cols[0]["next"]["title"] == "Prisha in progress"
    assert cols[1]["next"]["title"] == "Prapti daycare photos"


def test_running_all_day_span_is_still_upcoming() -> None:
    events = [day("2026-10-19", "Fall break", "school", end="2026-10-22",
                  persons=["prisha"], category="holiday")]
    col = run_hero(events)["persons"][0]
    assert col["next_holiday"]["title"] == "Fall break"


def test_next_holiday_is_per_person() -> None:
    events = [
        day("2026-10-22", "Picture day", "school", persons=["prisha"]),
        day("2026-11-03", "Daycare closed", persons=["prapti"], category="holiday"),
        day("2026-11-11", "Veterans Day", "school", persons=["prisha"],
            category="holiday"),
    ]
    prisha, prapti = run_hero(events)["persons"]
    assert prisha["next"]["title"] == "Picture day"
    assert prisha["next_holiday"]["title"] == "Veterans Day"
    assert prapti["next"] is None  # holidays never show as NEXT UP
    assert prapti["next_holiday"]["title"] == "Daycare closed"


def test_next_up_skips_holidays() -> None:
    events = [
        day("2026-11-03", "Election Day", "school", persons=["prisha"], category="holiday"),
        day("2026-11-25", "Early release", "school", persons=["prisha"]),
    ]
    prisha = run_hero(events)["persons"][0]
    assert prisha["next"]["start_date"] == "2026-11-25"
    assert prisha["next_holiday"]["start_date"] == "2026-11-03"


def test_next_up_is_none_with_only_holidays() -> None:
    events = [day("2026-11-03", "Election Day", "school", persons=["prisha"],
                  category="holiday")]
    prisha = run_hero(events)["persons"][0]
    assert prisha["next"] is None
    assert prisha["next_holiday"]["title"] == "Election Day"


def test_person_with_nothing_gets_nulls() -> None:
    events = [day("2026-10-22", "Picture day", "school", persons=["prisha"])]
    prapti = run_hero(events)["persons"][1]
    assert prapti == {"key": "prapti", "next": None, "next_holiday": None}


def test_family_pool_is_family_feed_events_matching_nobody() -> None:
    events = [
        day("2026-10-20", "Past family thing"),
        day("2026-10-22", "Prapti swim", persons=["prapti"]),
        day("2026-10-22", "Picture day", "school", persons=["prisha"]),
        day("2026-10-23", "Board meeting", "school"),  # nobody, but not family feed
        day("2026-10-24", "Dinner with Ana"),
        day("2026-10-25", "Pumpkin patch"),
        day("2026-10-26", "Third family thing"),
    ]
    family = run_hero(events)["family"]
    assert family["next"]["title"] == "Dinner with Ana"
    assert family["following"]["title"] == "Pumpkin patch"


# --- closed label ------------------------------------------------------------

LABELS = {"school": "School closed"}


def test_closed_label_strips_colon_tail() -> None:
    e = day("2026-11-03", "Uncapped Workday/Election Day: No School for Students",
            "school", category="holiday")
    assert closed_title(e, LABELS, {"holiday"}) == (
        "School closed – Uncapped Workday/Election Day"
    )


def test_closed_label_without_colon() -> None:
    e = day("2026-11-11", "Veterans Day", "school", category="holiday")
    assert closed_title(e, LABELS, {"holiday"}) == "School closed – Veterans Day"


def test_closed_label_leaves_unlabelled_feed_and_non_holidays() -> None:
    family = day("2026-11-03", "Daycare closed: all day", category="holiday")
    school = day("2026-11-05", "Early dismissal: 1pm", "school")
    assert closed_title(family, LABELS, {"holiday"}) == "Daycare closed: all day"
    assert closed_title(school, LABELS, {"holiday"}) == "Early dismissal: 1pm"


def test_closed_label_on_hero_holiday_only() -> None:
    raw = "Veterans Day: Schools Closed"
    events = [
        day("2026-10-22", "Picture day: bring smile", "school", persons=["prisha"]),
        day("2026-11-11", raw, "school", persons=["prisha"], category="holiday"),
    ]
    prisha = hero(events, TODAY, NOW, ROSTER, {"family"}, {"holiday"}, LABELS)["persons"][0]
    assert prisha["next"]["title"] == "Picture day: bring smile"
    assert prisha["next_holiday"]["title"] == "School closed – Veterans Day"
    assert events[1]["title"] == raw  # the grid's event is not mutated


def test_radar_uses_closed_label() -> None:
    events = [
        day("2026-11-03", "Election Day: No School", "school", category="holiday"),
        day("2026-11-05", "Early Dismissal: 1pm", "school"),
    ]
    titles = [r["title"] for r in radar(events, TODAY, 30, KW, LABELS, {"holiday"})]
    assert titles == ["School closed – Election Day", "Early Dismissal: 1pm"]


# --- radar -------------------------------------------------------------------

KW = ("no school", "holiday", "early dismissal")


def test_radar_window_and_keyword_match() -> None:
    events = [
        day("2026-10-20", "Holiday program"),                   # ended yesterday
        day("2026-10-19", "No School week", end="2026-10-21"),  # overlaps today
        day("2026-11-05", "Early Dismissal"),
        day("2026-11-10", "Picture day"),                       # no keyword
        day("2026-11-20", "Holiday party"),                     # day 30: in
        day("2026-11-21", "Holiday market"),                    # day 31: out
    ]
    titles = [r["title"] for r in radar(events, TODAY, 30, KW, {})]
    assert titles == ["No School week", "Early Dismissal", "Holiday party"]


def test_radar_dedupes_by_start_and_title() -> None:
    events = [
        day("2026-11-26", "Thanksgiving Holiday", "school", end="2026-11-27"),
        day("2026-11-26", "Thanksgiving Holiday", "family", end="2026-11-27"),
    ]
    assert radar(events, TODAY, 40, KW, {}) == [
        {"start_date": "2026-11-26", "end_date": "2026-11-27",
         "title": "Thanksgiving Holiday", "category": None}
    ]


def test_radar_caps_at_eight_chronological() -> None:
    events = [day(f"2026-10-{d}", f"Holiday {d}") for d in range(22, 32)]
    titles = [r["title"] for r in radar(events, TODAY, 30, KW, {})]
    assert titles == [f"Holiday {d}" for d in range(22, 30)]


# --- waste -------------------------------------------------------------------

REGULAR = "Yard Waste · Garbage"
RECYCLE = "Yard Waste · Recycling · Garbage"
BULKY = "Yard Waste · Bulky Waste · Garbage"


def trash(start: str, title: str) -> dict:
    return day(start, title, "trash")


def run_waste(events: list[dict], today: date = TODAY) -> dict:
    return waste(events, today, ("recycling",), ("bulky",))


def test_regular_week_with_items() -> None:
    result = run_waste([trash("2026-10-21", REGULAR), trash("2026-10-28", RECYCLE)])
    assert result["week_kind"] == "regular"
    assert result["next"] == {"date": "2026-10-21", "title": REGULAR,
                              "items": ["Yard Waste", "Garbage"]}
    assert result["following"]["date"] == "2026-10-28"


def test_recycling_week() -> None:
    result = run_waste([trash("2026-10-21", RECYCLE), trash("2026-10-28", REGULAR)])
    assert result["week_kind"] == "recycle"


def test_bulky_week() -> None:
    assert run_waste([trash("2026-10-21", BULKY)])["week_kind"] == "bulky"


def test_recycling_wins_when_bulky_and_recycling_share_a_pickup() -> None:
    title = "Yard Waste · Bulky Waste · Recycling · Garbage"
    assert run_waste([trash("2026-10-21", title)])["week_kind"] == "recycle"


def test_shared_day_from_the_live_feed_is_recycle() -> None:
    # Next week's alternate-Wednesday pickup, as the Concord feed titles it.
    title = ("Loose Leaf - Wednesday Week - Day 3 · Yard Waste · Bulky Waste"
             " · Recycling · Garbage")
    events = [trash("2026-10-21", REGULAR), trash("2026-10-28", title)]
    result = run_waste(events, date(2026, 10, 22))
    assert result["next"]["date"] == "2026-10-28"
    assert result["week_kind"] == "recycle"


def test_first_pickup_of_the_week_decides() -> None:
    # Sunday: Wednesday's regular pickup decides, not Saturday's recycling.
    events = [trash("2026-10-21", REGULAR), trash("2026-10-24", RECYCLE)]
    assert run_waste(events, date(2026, 10, 18))["week_kind"] == "regular"


def test_rolls_to_next_week_once_this_weeks_pickups_passed() -> None:
    events = [trash("2026-10-21", REGULAR), trash("2026-10-28", RECYCLE)]
    # Thursday: Wednesday's pickup has passed -> next week's recycling decides.
    result = run_waste(events, date(2026, 10, 22))
    assert result["next"]["date"] == "2026-10-28"
    assert result["week_kind"] == "recycle"
    assert result["following"] is None


def test_non_pickup_trash_feed_events_are_ignored() -> None:
    events = [trash("2026-10-21", "HHW Collection"),
              trash("2026-10-24", "Safe disposal event")]
    assert run_waste(events) == {"next": None, "following": None,
                                 "week_kind": "regular"}


def test_pickups_on_the_same_day_merge() -> None:
    events = [trash("2026-10-21", "Garbage"),
              day("2026-10-21", "Recycling · Garbage", "family")]
    result = run_waste(events)
    assert result["next"]["items"] == ["Garbage", "Recycling"]
    assert result["week_kind"] == "recycle"
