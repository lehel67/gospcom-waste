"""Texts for notifications and calendar events, in the Home Assistant language."""

from __future__ import annotations

from datetime import date

from .schedule import BIODEGRADABLE, MIXED, SELECTIVE, Collection

TEXTS: dict[str, dict[str, str]] = {
    "hu": {
        MIXED: "vegyes háztartási",
        SELECTIVE: "szelektív",
        BIODEGRADABLE: "lebomló (zöld)",
        "title": "🗑️ Holnap szemétszállítás",
        "reminder": "Holnap ({day}) viszik: {types} hulladék. Ne felejtsd el kitenni!",
        "mixed_note": "A vegyes háztartási hulladékot is viszik!",
        "moved": "Ünnep miatt {planned} helyett.",
        "calendar": "🗑️ Szemétszállítás: {types}",
        "drop_off": "♻️ Szelektív és elektronikai hulladékgyűjtő nap",
        "weekdays": "hétfő,kedd,szerda,csütörtök,péntek,szombat,vasárnap",
        "months": "jan.,febr.,márc.,ápr.,máj.,jún.,júl.,aug.,szept.,okt.,nov.,dec.",
        "date": "{weekday}, {month} {day}.",
    },
    "ro": {
        MIXED: "menajere",
        SELECTIVE: "selective",
        BIODEGRADABLE: "biodegradabile",
        "title": "🗑️ Mâine se colectează gunoiul",
        "reminder": "Mâine ({day}) se colectează deșeurile: {types}. Nu uita să le scoți!",
        "mixed_note": "Se colectează și deșeurile menajere!",
        "moved": "Mutat de pe {planned} din cauza sărbătorii.",
        "calendar": "🗑️ Colectare deșeuri: {types}",
        "drop_off": "♻️ Zi de colectare a deșeurilor selective și electronice",
        "weekdays": "luni,marți,miercuri,joi,vineri,sâmbătă,duminică",
        "months": "ian.,feb.,mar.,apr.,mai,iun.,iul.,aug.,sept.,oct.,nov.,dec.",
        "date": "{weekday}, {day} {month}",
    },
    "en": {
        MIXED: "mixed household",
        SELECTIVE: "selective",
        BIODEGRADABLE: "biodegradable",
        "title": "🗑️ Waste collection tomorrow",
        "reminder": "Tomorrow ({day}) collection: {types} waste. Don't forget to put it out!",
        "mixed_note": "Mixed household waste is collected too!",
        "moved": "Moved from {planned} because of a holiday.",
        "calendar": "🗑️ Waste collection: {types}",
        "drop_off": "♻️ Selective and electronic waste drop-off day",
        "weekdays": "Monday,Tuesday,Wednesday,Thursday,Friday,Saturday,Sunday",
        "months": "Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec",
        "date": "{weekday}, {day} {month}",
    },
}


def texts(language: str | None) -> dict[str, str]:
    """Return the texts of a language, English if not known."""
    return TEXTS.get((language or "en").split("-")[0], TEXTS["en"])


def day_text(day: date, language: str | None) -> str:
    """Return a short, readable date such as "kedd, nov. 10."."""
    text = texts(language)
    return text["date"].format(
        weekday=text["weekdays"].split(",")[day.weekday()],
        month=text["months"].split(",")[day.month - 1],
        day=day.day,
    )


def types_text(collection: Collection, language: str | None) -> str:
    """Return the waste types as a readable list."""
    text = texts(language)
    names = [text[kind] for kind in collection.types]
    separator = {"hu": " és ", "ro": " și "}.get((language or "en")[:2], " and ")
    return ", ".join(names[:-1]) + separator + names[-1] if len(names) > 1 else names[0]


def reminder_message(collection: Collection, language: str | None) -> str:
    """Return the evening reminder of a collection."""
    text = texts(language)
    message = text["reminder"].format(
        day=day_text(collection.day, language), types=types_text(collection, language)
    )
    if collection.has_mixed:
        message += " " + text["mixed_note"]
    if collection.moved:
        message += " " + text["moved"].format(planned=day_text(collection.planned, language))
    return message
