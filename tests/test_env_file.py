""".env model: round-trip, apply, diff, quoting, schema (pure, no I/O)."""

from datetime import date

from app import env_file as ef

SAMPLE = (
    "# Copy to .env\r\n"
    "# ---------------\r\n"
    "# Weather\r\n"
    "# ---------------\r\n"
    "# Where we are.\r\n"
    "WEATHER_LAT=35.3\r\n"
    "WEATHER_LON=-80.6\r\n"
    "\r\n"
    "  \r\n"
    "CAL_SCHOOL_COLOR=#74c0fc  # inline comment\r\n"
    "NWS_USER_AGENT='(Wall, a@b.c)'\r\n"
    "QUOTED=\"it's # fine\"\r\n"
    "LAST=no-newline"
)


def test_round_trip_is_byte_identical_with_crlf_comments_and_blanks() -> None:
    entries = ef.parse(SAMPLE)
    assert ef.render(entries) == SAMPLE
    assert [e.kind for e in entries[:9]] == ["comment"] * 5 + ["pair", "pair", "blank", "blank"]


def test_values_follow_dotenv_syntax() -> None:
    vals = ef.values(ef.parse(SAMPLE))
    assert vals["CAL_SCHOOL_COLOR"] == "#74c0fc"
    assert vals["NWS_USER_AGENT"] == "(Wall, a@b.c)"
    assert vals["QUOTED"] == "it's # fine"
    assert vals["LAST"] == "no-newline"


def test_apply_updates_in_place_keeping_crlf() -> None:
    out = ef.render(ef.apply(ef.parse(SAMPLE), {"WEATHER_LAT": "36.0"}))
    assert out == SAMPLE.replace("WEATHER_LAT=35.3\r\n", "WEATHER_LAT=36.0\r\n")


def test_apply_removes_and_appends_under_a_dated_comment() -> None:
    changes = {"WEATHER_LON": None, "PHOTO_INTERVAL_SECONDS": "15"}
    out = ef.render(ef.apply(ef.parse(SAMPLE), changes, today=date(2026, 10, 19)))
    assert "WEATHER_LON" not in out
    assert out.endswith(
        "LAST=no-newline\r\n\r\n# Added via /admin 2026-10-19\r\nPHOTO_INTERVAL_SECONDS=15\r\n"
    )


def test_apply_unchanged_value_keeps_the_original_line() -> None:
    entries = ef.parse(SAMPLE)
    assert ef.render(ef.apply(entries, {"CAL_SCHOOL_COLOR": "#74c0fc"})) == SAMPLE


def test_quoting_only_when_needed_and_it_reparses() -> None:
    assert ef.quote("plain value, with commas") == "plain value, with commas"
    assert ef.quote("#ff0000") == "'#ff0000'"
    assert ef.quote(" padded ") == "' padded '"
    for value in ("#ff0000", " padded ", "it's #1", "back\\slash #"):
        text = ef.render(ef.apply([], {"K": value}))
        assert ef.values(ef.parse(text))["K"] == value


def test_diff_reports_drift() -> None:
    current = ef.parse("A=1\nB=2\nEXTRA=x\n")
    example = ef.parse("A=1\nB=3\nNEW=\n")
    assert ef.diff(current, example) == {
        "missing_in_env": ["NEW"],
        "unknown_in_env": ["EXTRA"],
        "changed_from_default": ["B"],
    }


def test_schema_sections_and_comments() -> None:
    sections = ef.schema(ef.parse(SAMPLE))
    weather = next(s for s in sections if s["title"] == "Weather")
    lat, lon = weather["keys"][:2]
    assert (lat["key"], lat["default"], lat["comment"]) == ("WEATHER_LAT", "35.3", "Where we are.")
    assert lon["comment"] == "Where we are."  # same run of keys
    assert weather["keys"][2]["comment"] == ""  # after a blank line
