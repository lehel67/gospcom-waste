"""Tests for the schedule rules."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pytest

from custom_components.gospcom_waste.schedule import (
    DATA_DIR,
    MIXED,
    load_schedule,
    orthodox_easter,
    romanian_holidays,
    street_key,
)


@pytest.fixture(scope="module")
def schedule():
    return load_schedule()


def test_streets(schedule) -> None:
    """Every street of the operator is there, courtyards one by one."""
    assert len(schedule.streets) == 159
    assert schedule.streets[street_key("15-ös udvartér")].ro == "Curtea 15"
    assert schedule.streets[street_key("24-es udvartér")].weekday == 2
    assert schedule.streets[street_key("Patak utca")].ro == "Râului"
    assert schedule.streets[street_key("Nyujtód")].kind == "village"


def test_holidays() -> None:
    """Orthodox Easter and the movable holidays are right."""
    assert orthodox_easter(2026) == date(2026, 4, 12)
    assert orthodox_easter(2027) == date(2027, 5, 2)
    days = romanian_holidays(2026)
    assert date(2026, 4, 10) in days  # Good Friday
    assert date(2026, 6, 1) in days  # Pentecost Monday and Children's Day
    assert date(2026, 11, 30) in days


def test_weekly_and_mixed(schedule) -> None:
    """Selective every week, mixed in the odd weeks only."""
    street = schedule.streets[street_key("Gábor Áron tér")]
    found = schedule.collections(street, date(2026, 11, 9), date(2026, 11, 30))
    assert [(c.day, c.has_mixed) for c in found] == [
        (date(2026, 11, 10), False),
        (date(2026, 11, 17), True),
        (date(2026, 11, 24), False),
    ]


def test_holiday_moves_to_next_working_day(schedule) -> None:
    """1 December moves to the 2nd, Christmas Friday to Monday, types kept."""
    tuesday = schedule.streets[street_key("Gábor Áron tér")]
    moved = schedule.collections(tuesday, date(2026, 12, 1), date(2026, 12, 3))
    assert len(moved) == 1
    assert moved[0].day == date(2026, 12, 2)
    assert moved[0].planned == date(2026, 12, 1)
    assert MIXED in moved[0].types

    friday = schedule.streets[street_key("Kert utca")]
    christmas = schedule.collections(friday, date(2026, 12, 24), date(2026, 12, 31))
    assert [(c.day, c.planned, c.has_mixed) for c in christmas] == [
        (date(2026, 12, 28), date(2026, 12, 25), False)
    ]

    # 1 and 2 January: Thursday and Friday streets both go on Monday the 5th.
    thursday = schedule.streets[street_key("Domb utca")]
    assert [c.day for c in schedule.collections(thursday, date(2026, 1, 1), date(2026, 1, 6))] == [
        date(2026, 1, 5)
    ]


def test_no_data_after_the_year(schedule) -> None:
    """Without data for 2027 there is nothing to show."""
    street = schedule.streets[street_key("Gábor Áron tér")]
    assert schedule.collections(street, date(2027, 1, 10), date(2027, 2, 28)) == []
    # The data of 2026 lasts until the end of its last ISO week.
    assert schedule.last_day == date(2027, 1, 3)


def test_drop_off_days(schedule) -> None:
    """The drop-off days of 2026."""
    assert [d.day for d in schedule.drop_off_days(date(2026, 11, 1), date(2026, 12, 31))] == [
        date(2026, 11, 13)
    ]


def _year_file(folder: Path, year: int, weekday: str, mixed_weeks: list[int]) -> None:
    raw = json.loads((DATA_DIR / "2026.json").read_text("utf-8"))
    for street in raw["streets"]:
        if street["hu"] == "Gábor Áron tér":
            street["mixed_day"] = weekday
    raw["houses"]["mixed_iso_weeks"] = mixed_weeks
    raw["collection_days"]["dates"] = []
    (folder / f"{year}.json").write_text(json.dumps(raw), "utf-8")


def test_next_year_file_waits_for_its_year(tmp_path: Path) -> None:
    """A 2027 file already in place changes nothing in 2026."""
    _year_file(tmp_path, 2027, "wednesday", list(range(2, 53, 2)))
    (tmp_path / "2028.json").write_text("{not json", "utf-8")  # skipped
    (tmp_path / "notes.json").write_text("{}", "utf-8")  # not a year, ignored
    schedule = load_schedule(tmp_path)
    assert sorted(schedule.years) == [2026, 2027]

    street = schedule.streets[street_key("Gábor Áron tér")]
    found = schedule.collections(street, date(2026, 12, 21), date(2027, 1, 20))
    assert [(c.day, c.has_mixed) for c in found] == [
        (date(2026, 12, 22), False),  # 2026 rules: Tuesday, week 52
        (date(2026, 12, 29), True),  # Tuesday, week 53 of 2026
        # 2027 rules: Wednesday, week 1 (odd, no mixed); 6-7 January are holidays.
        (date(2027, 1, 8), False),
        (date(2027, 1, 13), True),  # week 2, even -> mixed in the 2027 file
        (date(2027, 1, 20), False),
    ]
    # Looking back still works with the old year's rules.
    back = schedule.collections(street, date(2026, 3, 1), date(2026, 3, 12))
    assert [c.day for c in back] == [date(2026, 3, 3), date(2026, 3, 10)]


def test_user_file_replaces_shipped_one(tmp_path: Path) -> None:
    """A corrected 2026 file in the config folder wins over the shipped one."""
    _year_file(tmp_path, 2026, "thursday", [])
    schedule = load_schedule(tmp_path)
    street = schedule.streets[street_key("Gábor Áron tér")]
    found = schedule.collections(street, date(2026, 11, 9), date(2026, 11, 22))
    assert [(c.day, c.has_mixed) for c in found] == [
        (date(2026, 11, 12), False),
        (date(2026, 11, 19), False),
    ]
