"""The waste collection schedule of one street, worked out from the yearly data.

Kept free of Home Assistant objects so it is easy to test.

Rules (Gosp-Com, Kézdivásárhely):
- Every week, on the street's weekday, selective and biodegradable waste is taken.
- In the weeks listed as mixed weeks (2026: the odd ISO weeks), mixed household
  waste is taken on the same day too.
- When that day is a public holiday, the collection moves to the next working
  day (Monday to Friday, not a holiday). It keeps the waste types of its own week.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import cache
import json
import logging
from pathlib import Path
from typing import Any

MIXED = "mixed"
SELECTIVE = "selective"
BIODEGRADABLE = "biodegradable"
TYPE_ORDER = (MIXED, SELECTIVE, BIODEGRADABLE)

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
DATA_DIR = Path(__file__).parent / "data"
_LOGGER = logging.getLogger(__name__)


def orthodox_easter(year: int) -> date:
    """Return the Orthodox Easter Sunday (Meeus' Julian algorithm, in Gregorian dates)."""
    a, b, c = year % 4, year % 7, year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month, day = divmod(d + e + 114, 31)
    julian = date(year, month, day + 1)
    # The Julian calendar is 13 days behind in 1900-2099.
    return julian + timedelta(days=13)


@cache
def romanian_holidays(year: int) -> frozenset[date]:
    """Return the public holidays of Romania in a year."""
    easter = orthodox_easter(year)
    fixed = [
        (1, 1), (1, 2), (1, 6), (1, 7), (1, 24), (5, 1), (6, 1),
        (8, 15), (11, 30), (12, 1), (12, 25), (12, 26),
    ]
    days = {date(year, month, day) for month, day in fixed}
    for offset in (-2, 0, 1, 49, 50):  # Good Friday, Easter, Pentecost (Sunday, Monday)
        days.add(easter + timedelta(days=offset))
    return frozenset(days)


def is_working_day(day: date) -> bool:
    """Return if the day is Monday to Friday and not a public holiday."""
    return day.weekday() < 5 and day not in romanian_holidays(day.year)


def next_working_day(day: date) -> date:
    """Return the day itself if it is a working day, else the next working day."""
    while not is_working_day(day):
        day += timedelta(days=1)
    return day


@dataclass(frozen=True)
class Street:
    """A street, courtyard or village with its collection weekday."""

    key: str
    hu: str
    ro: str
    kind: str
    weekday: int


@dataclass(frozen=True)
class Collection:
    """One collection: the day, the waste types, and the planned day if it moved."""

    day: date
    types: tuple[str, ...]
    planned: date

    @property
    def moved(self) -> bool:
        """Return if a holiday moved the collection to a later day."""
        return self.day != self.planned

    @property
    def has_mixed(self) -> bool:
        """Return if mixed household waste is taken too."""
        return MIXED in self.types


@dataclass(frozen=True)
class DropOffDay:
    """A day when selective and electronic waste can be brought to collection points."""

    day: date
    hours: str
    places: tuple[str, ...]


@dataclass
class YearData:
    """The schedule data of one year: its weeks, streets and drop-off days.

    A year's data covers the ISO weeks of that year, from the Monday of week 1
    to the Sunday of its last week, so a week is never split between two files.
    """

    year: int
    mixed_weeks: frozenset[int]
    streets: dict[str, Street]
    drop_off: list[DropOffDay] = field(default_factory=list)

    @property
    def first_day(self) -> date:
        """Return the Monday of ISO week 1."""
        return date.fromisocalendar(self.year, 1, 1)

    @property
    def last_day(self) -> date:
        """Return the Sunday of the last ISO week."""
        return date.fromisocalendar(self.year + 1, 1, 1) - timedelta(days=1)


def street_key(name_hu: str) -> str:
    """Return a stable key for a street from its Hungarian name."""
    return name_hu.casefold().replace(" ", "_")


def _parse_year(year: int, raw: dict[str, Any]) -> YearData:
    drop = raw.get("collection_days", {})
    return YearData(
        year=year,
        mixed_weeks=frozenset(raw["houses"]["mixed_iso_weeks"]),
        streets={
            street_key(item["hu"]): Street(
                key=street_key(item["hu"]),
                hu=item["hu"],
                ro=item["ro"],
                kind=item["kind"],
                weekday=WEEKDAYS.index(item["mixed_day"]),
            )
            for item in raw["streets"]
        },
        drop_off=[
            DropOffDay(
                day=date.fromisoformat(day),
                hours=drop.get("hours", ""),
                places=tuple(drop.get("places_hu", [])),
            )
            for day in drop.get("dates", [])
        ],
    )


class Schedule:
    """The yearly data files; each year with its own streets, weekdays and weeks."""

    def __init__(self, years: dict[int, dict[str, Any]]) -> None:
        """Build the schedule from the parsed yearly data files."""
        self.years: dict[int, YearData] = {
            year: _parse_year(year, raw) for year, raw in sorted(years.items())
        }
        # Every street of every year, the newest names winning, to choose from.
        self.streets: dict[str, Street] = {}
        for data in self.years.values():
            self.streets.update(data.streets)

    @property
    def last_day(self) -> date:
        """Return the last day the data covers."""
        return max(data.last_day for data in self.years.values())

    def collections(self, street: Street, start: date, end: date) -> list[Collection]:
        """Return the collections of a street that fall between start and end (inclusive).

        Each week is worked out with the data of its own year, so a new year's
        file that is already in place changes nothing before that year starts.
        """
        found: list[Collection] = []
        for data in self.years.values():
            year_street = data.streets.get(street.key)
            if year_street is None:
                continue
            # Start a week early so a collection moved into the range is not missed.
            first = max(data.first_day, start - timedelta(days=7))
            last = min(data.last_day, end)
            planned = first + timedelta(days=(year_street.weekday - first.weekday()) % 7)
            while planned <= last:
                types = (
                    TYPE_ORDER
                    if planned.isocalendar().week in data.mixed_weeks
                    else (SELECTIVE, BIODEGRADABLE)
                )
                day = next_working_day(planned)
                if start <= day <= end:
                    found.append(Collection(day=day, types=types, planned=planned))
                planned += timedelta(days=7)
        return sorted(found, key=lambda collection: collection.day)

    def next_collections(self, street: Street, today: date, count: int = 10) -> list[Collection]:
        """Return the next collections from today on (today included)."""
        return self.collections(street, today, today + timedelta(days=7 * count))[:count]

    def drop_off_days(self, start: date, end: date) -> list[DropOffDay]:
        """Return the drop-off days between start and end (inclusive)."""
        return [
            drop
            for data in self.years.values()
            for drop in data.drop_off
            if start <= drop.day <= end
        ]


def load_schedule(extra_dir: Path | None = None) -> Schedule:
    """Read every yearly data file (2026.json, 2027.json, ...). Does blocking I/O.

    Files in extra_dir (the user's config folder) replace the shipped file of
    the same year, so a new year can be added before an integration update.
    """
    files: dict[int, Path] = {}
    for folder in (DATA_DIR, extra_dir):
        if folder is None or not folder.is_dir():
            continue
        for path in folder.glob("*.json"):
            if path.stem.isdigit() and len(path.stem) == 4:
                files[int(path.stem)] = path
    years: dict[int, dict[str, Any]] = {}
    for year, path in sorted(files.items()):
        try:
            raw = json.loads(path.read_text("utf-8"))
            _parse_year(year, raw)
        except (OSError, ValueError, KeyError, TypeError) as err:
            _LOGGER.error("Skipping the invalid waste schedule file %s: %s", path, err)
            continue
        years[year] = raw
    return Schedule(years)
