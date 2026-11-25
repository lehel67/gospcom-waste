"""Reads the bills from the Gosp-Com customer account (www.gosp-com.ro/account).

The parsing functions are pure (plain strings in, dataclasses out), so they can be
tested with saved pages. Only the account pages are read: the site is never asked
to pay, change a setting or download an invoice (downloading one confirms receipt).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
import re
from typing import Any

import aiohttp

BASE_URL = "https://www.gosp-com.ro"
LOGIN_PATH = "/account/login"
INVOICES_PATH = "/account/invoices"
TIMEOUT = aiohttp.ClientTimeout(total=30)

HU_MONTHS = {
    "jan": 1, "febr": 2, "márc": 3, "marc": 3, "ápr": 4, "apr": 4, "máj": 5, "maj": 5,
    "jún": 6, "jun": 6, "júl": 7, "jul": 7, "aug": 8, "szept": 9, "szep": 9,
    "okt": 10, "nov": 11, "dec": 12,
}
RO_MONTHS = {
    "ian": 1, "feb": 2, "mar": 3, "apr": 4, "mai": 5, "iun": 6, "iul": 7,
    "aug": 8, "sep": 9, "oct": 10, "noi": 11, "nov": 11, "dec": 12,
}


class AuthError(Exception):
    """The e-mail address or the password was not accepted."""


class AccountError(Exception):
    """The site could not be reached or returned something unexpected."""


@dataclass(frozen=True)
class Invoice:
    """One invoice as the account page lists it."""

    number: str
    issued: date
    amount: float
    paid: float
    pdf_url: str | None = None

    @property
    def rest(self) -> float:
        """What is still to pay on this invoice."""
        return round(max(self.amount - self.paid, 0.0), 2)

    def as_dict(self) -> dict[str, Any]:
        """Attribute form, in the shape the Számla-naptár integration reads."""
        return {
            "invoice_number": self.number,
            "issue_date": self.issued.isoformat(),
            "amount": self.amount,
            "paid": self.paid,
            "rest": self.rest,
            "pdf_url": self.pdf_url,
        }


@dataclass
class ClientAccount:
    """The bills of one customer code."""

    code: str
    invoices: list[Invoice] = field(default_factory=list)  # newest first
    reported_due: float | None = None  # "A jelenleg fizetendő összeg" on the page

    @property
    def total_due(self) -> float:
        """What is to pay now: the page's own figure, else the sum of the open invoices."""
        if self.reported_due is not None:
            return self.reported_due
        return round(sum(inv.rest for inv in self.invoices), 2)

    @property
    def open_invoices(self) -> list[Invoice]:
        """Invoices not fully paid yet."""
        return [inv for inv in self.invoices if inv.rest > 0.005]

    @property
    def last_invoice(self) -> Invoice | None:
        """The newest invoice."""
        return self.invoices[0] if self.invoices else None


# ------------------------------------------------------------------ parsing


def parse_amount(text: str) -> float | None:
    """'94,84 lej' / '1.234,50 lei' / '10\xa0lej' / '-99,97 lej' → float."""
    match = re.search(r"-?\d[\d.\s\xa0]*(?:,\d+)?", text or "")
    if not match:
        return None
    raw = re.sub(r"[\s\xa0]", "", match.group(0)).replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def parse_date(text: str) -> date | None:
    """'2026. okt. 26.' (hu), '26 oct. 2026' / '26.10.2026' (ro) → date."""
    low = (text or "").strip().lower()
    if m := re.search(r"(\d{4})\.\s*([a-záéíóöőúüű]+)\.?\s*(\d{1,2})", low):
        year, month, day = int(m.group(1)), HU_MONTHS.get(m.group(2)), int(m.group(3))
    elif m := re.search(r"(\d{1,2})\s+([a-zăâîșşțţ]+)\.?\s+(\d{4})", low):
        day, month, year = int(m.group(1)), RO_MONTHS.get(m.group(2)[:3]), int(m.group(3))
    elif m := re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", low):
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        return None
    if not month:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


class _PageParser(HTMLParser):
    """Collects the login form, the invoice rows and the customer codes of a page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: list[dict[str, Any]] = []
        self.client_codes: list[str] = []
        self.has_logout = False
        self.rows: list[dict[str, Any]] = []
        self.text: list[str] = []
        self._row: dict[str, Any] | None = None
        self._row_depth = 0
        self._cell: list[str] | None = None
        self._cell_depth = 0
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        classes = a.get("class", "").split()
        if tag == "form":
            self.forms.append({"action": a.get("action", ""), "inputs": []})
        elif tag == "input" and self.forms:
            self.forms[-1]["inputs"].append(a)
        elif tag == "a":
            href = a.get("href", "")
            if "/account/logout" in href:
                self.has_logout = True
            if m := re.search(r"/account/invoices\?(?:.*&)?cc=(\d+)", href):
                if m.group(1) not in self.client_codes:
                    self.client_codes.append(m.group(1))
            if self._row is not None and "InvoiceHost" in href:
                self._row["pdf_url"] = href
        if tag in ("br", "img", "input", "meta", "link", "hr"):
            return  # void elements don't change the depth
        self._depth += 1
        if "invoice-list-item" in classes:
            self._row, self._row_depth = {"cells": [], "pdf_url": None}, self._depth
        elif self._row is not None and "detail-info-table-cell" in classes:
            self._cell, self._cell_depth = [], self._depth

    def handle_endtag(self, tag: str) -> None:
        if tag in ("br", "img", "input", "meta", "link", "hr"):
            return
        if self._cell is not None and self._depth == self._cell_depth:
            self._row["cells"].append(" ".join("".join(self._cell).split()))
            self._cell = None
        if self._row is not None and self._depth == self._row_depth:
            self.rows.append(self._row)
            self._row = None
        self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)
        self.text.append(data)


def parse_login_form(html: str, email: str, password: str) -> tuple[str, dict[str, str]] | None:
    """Fill the login form the way a browser would: hidden fields as they are, the
    e-mail and password in, 'keep me signed in' ticked, every other box left empty
    (one of them is a trap for robots)."""
    parser = _PageParser()
    parser.feed(html)
    for form in parser.forms:
        names = [i.get("name", "") for i in form["inputs"]]
        if not any(n.endswith("[password]") or n == "password" for n in names):
            continue
        data: dict[str, str] = {}
        for item in form["inputs"]:
            name, kind = item.get("name", ""), item.get("type", "text").lower()
            if not name:
                continue
            if kind == "password":
                data[name] = password
            elif kind == "email" or name.endswith("[email]"):
                data[name] = email
            elif kind == "hidden":
                data[name] = item.get("value", "")
            elif kind == "checkbox" and name.endswith("[remember]"):
                data[name] = item.get("value") or "1"
        return form["action"] or LOGIN_PATH, data
    return None


def parse_invoices_page(html: str) -> tuple[bool, list[str], list[Invoice], float | None]:
    """Return (signed in, customer codes, invoices newest first, amount due on the page)."""
    parser = _PageParser()
    parser.feed(html)
    invoices: list[Invoice] = []
    for row in parser.rows:
        # cells come in label/value pairs: date, number, amount, paid
        values = row["cells"][1::2]
        if len(values) < 4:
            continue
        issued, amount, paid = parse_date(values[0]), parse_amount(values[2]), parse_amount(values[3])
        number = re.sub(r"\D", "", values[1])
        if issued is None or amount is None or not number:
            continue
        invoices.append(Invoice(number, issued, amount, paid or 0.0, row["pdf_url"]))
    invoices.sort(key=lambda inv: (inv.issued, inv.number), reverse=True)
    text = " ".join(" ".join(parser.text).split())
    due = None
    if m := re.search(
        r"(?:fizetendő összeg|suma (?:de plată|de plata|datorată|datorata)[^:]*):\s*(-?[\d.,]+)",
        text,
        re.IGNORECASE,
    ):
        due = parse_amount(m.group(1))
    return parser.has_logout, parser.client_codes, invoices, due


# ------------------------------------------------------------------ client


class GospcomAccountClient:
    """Signs in with the customer's e-mail and password and reads the invoices."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        """The session should have its own cookie jar."""
        self._session = session
        self._email = email
        self._password = password

    async def _get(self, path: str) -> tuple[str, str]:
        try:
            async with self._session.get(BASE_URL + path, timeout=TIMEOUT) as resp:
                resp.raise_for_status()
                return str(resp.url), await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise AccountError(f"GET {path}: {err}") from err

    async def async_login(self) -> None:
        """Sign in. Raises AuthError when the credentials are refused."""
        _, html = await self._get(LOGIN_PATH)
        form = parse_login_form(html, self._email, self._password)
        if form is None:
            raise AccountError("login form not found")
        action, data = form
        url = action if action.startswith("http") else BASE_URL + action
        try:
            async with self._session.post(
                url, data=data, timeout=TIMEOUT, headers={"Referer": BASE_URL + LOGIN_PATH}
            ) as resp:
                resp.raise_for_status()
                body = await resp.text()
                final = str(resp.url)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise AccountError(f"login: {err}") from err
        if LOGIN_PATH in final and "/account/logout" not in body:
            raise AuthError("the e-mail address or the password was not accepted")

    async def _invoices_html(self, code: str | None) -> str:
        path = INVOICES_PATH + (f"?cc={code}" if code else "")
        final, html = await self._get(path)
        if LOGIN_PATH in final:  # session expired: sign in once more
            await self.async_login()
            final, html = await self._get(path)
            if LOGIN_PATH in final:
                raise AuthError("signed out right after signing in")
        return html

    async def async_fetch(self) -> dict[str, ClientAccount]:
        """Return the bills of every customer code on the account."""
        html = await self._invoices_html(None)
        signed_in, codes, invoices, due = parse_invoices_page(html)
        if not signed_in:
            raise AccountError("the invoices page did not load")
        if not codes:
            raise AccountError("no customer code on the account")
        if len(codes) == 1:  # the page already shows the only customer code
            return {codes[0]: ClientAccount(codes[0], invoices, due)}
        accounts = {}
        for code in codes:
            _, _, invoices, due = parse_invoices_page(await self._invoices_html(code))
            accounts[code] = ClientAccount(code, invoices, due)
        return accounts
