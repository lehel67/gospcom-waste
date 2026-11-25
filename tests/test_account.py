"""Tests of the account page parsers (no Home Assistant needed)."""
import importlib.util, sys, pathlib
from datetime import date

spec = importlib.util.spec_from_file_location(
    "gospcom_account", pathlib.Path(__file__).parents[1] / "custom_components" / "gospcom_waste" / "account.py")
account = importlib.util.module_from_spec(spec); sys.modules["gospcom_account"] = account; spec.loader.exec_module(account)

ITEM = ('<div class="invoice-list-item"><div class="detail-info-table-wrapper">'
 '<div class="detail-info-table"><div class="detail-info-table-cell">Dátum</div><div class="detail-info-table-cell"><span class="text-success">{d}</span></div></div>'
 '<div class="detail-info-table"><div class="detail-info-table-cell">Szám</div><div class="detail-info-table-cell"><span class="bold">{n}</span></div></div>'
 '<div class="detail-info-table"><div class="detail-info-table-cell">Számla értéke</div><div class="detail-info-table-cell">{a}&nbsp;lej</div></div>'
 '<div class="detail-info-table"><div class="detail-info-table-cell">Fizetés</div><div class="detail-info-table-cell">{p}&nbsp;lej</div></div>'
 '<div class="detail-info-table-raw"><div><a href="https://facturi.gosp-com.ro/InvoiceHost/?id={n}X" target="_blank"><span class="icesym is-download"></span> Számla letöltése</a></div></div></div></div>')

PAGE = ('<html><body><a href="/account/logout">Kijelentkezés</a>'
 '<ul><li><a href="/account/invoices?cc=111111">X</a></li></ul>'
 '<p>A jelenleg fizetendő összeg: 10,53</p><br><img src="x">'
 + ITEM.format(d="2026. szept. 30.", n="3837439", a="94,84", p="94,31")
 + ITEM.format(d="2026. okt. 26.", n="3839559", a="10", p="0")
 + ITEM.format(d="2020. jún. 5.", n="3528961", a="-99,97", p="-99,97")
 + '</body></html>')

def test_invoices():
    signed_in, codes, invoices, due = account.parse_invoices_page(PAGE)
    assert signed_in and codes == ["111111"] and due == 10.53
    assert [i.number for i in invoices] == ["3839559", "3837439", "3528961"]
    first = invoices[0]
    assert first.issued == date(2026, 10, 26) and first.amount == 10 and first.paid == 0 and first.rest == 10
    assert invoices[1].rest == 0.53
    assert invoices[1].pdf_url.endswith("3837439X")
    acc = account.ClientAccount("111111", invoices, None)
    assert acc.total_due == 10.53 and len(acc.open_invoices) == 2

def test_dates_amounts():
    assert account.parse_date("2026. márc. 31.") == date(2026, 3, 31)
    assert account.parse_date("2026. máj. 31.") == date(2026, 5, 31)
    assert account.parse_date("31 mai 2026") == date(2026, 5, 31)
    assert account.parse_date("26 oct. 2026") == date(2026, 10, 26)
    assert account.parse_date("26.10.2026") == date(2026, 10, 26)
    assert account.parse_amount("1.234,50 lei") == 1234.5
    assert account.parse_amount("-99,97\xa0lej") == -99.97

LOGIN = ('<form method="post" action="https://www.gosp-com.ro/account/login?returnurl=%2Faccount%2Finvoices">'
 '<input type="hidden" name="frontend-csrf" value="tok">'
 '<input type="email" name="FMLogin[email]"><input type="password" name="FMLogin[password]">'
 '<input type="hidden" name="FMLogin[remember]" value="0"><input type="checkbox" name="FMLogin[remember]" value="1">'
 '<input type="checkbox" name="FMLogin[iujaesiiiook]" value="1"><button type="submit"></button></form>')

def test_login_form():
    action, data = account.parse_login_form(LOGIN, "a@b.c", "pw")
    assert action.startswith("https://www.gosp-com.ro/account/login")
    assert data == {"frontend-csrf": "tok", "FMLogin[email]": "a@b.c", "FMLogin[password]": "pw",
                    "FMLogin[remember]": "1"}
