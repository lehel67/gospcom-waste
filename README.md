# Gosp-Com szemétszállítás – Home Assistant

[Magyar](#magyar) | [Română](#română) | [English](#english)

---

## Magyar

Mikor és milyen szemetet visznek a te utcádban **Kézdivásárhelyen, Nyújtódon, Szászfaluban és Sárfalván** (Gosp-Com SRL). Visszaszámlál a következő szállításig, este szól, hogy holnap mit kell kitenni, és naptárban mutatja az egész évet.

Nem kell hozzá internetkapcsolat vagy fiók: a menetrend az integrációban van, a [Gosp-Com hivatalos programja](https://www.gosp-com.ro/hu/hulladekelszallitas-kezdivasarhelyen-nyujtodon-szaszfaluban-es-sarfalvan) alapján.

### A szabály (2026)

- **Minden héten**, az utcád napján: **szelektív és lebomló (zöld)** hulladék.
- **Minden második héten** (a programban sárgával jelölt, páratlan hetek) ugyanazon a napon a **vegyes háztartási** hulladékot is viszik.
- Ha a szállítás napja **munkaszüneti nap**, a **következő munkanapon** viszik. A román ünnepnapokat (a mozgó ortodox húsvétot és pünkösdöt is) az integráció magától számolja.

### Telepítés

**HACS:** HACS → jobb felül a három pont → **Egyéni tárolók** → `https://github.com/lehel67/ha-gospcom-waste`, típus: **Integráció** → Letöltés → Home Assistant újraindítása.

**Kézzel:** a `custom_components/gospcom_waste` mappa a `config/custom_components/` alá, majd újraindítás.

### Beállítás

**Beállítások → Eszközök és szolgáltatások → Integráció hozzáadása → Gosp-Com szemétszállítás**

- **Utca, udvartér vagy falu**: a listában magyarul és románul is szerepel (pl. „Patak utca (Râului)”, „15-ös udvartér (Curtea 15)”, „Nyujtód (Lunga)”).
- **Emlékeztető időpontja**: az előző nap ennyikor szól (alapból 19:00).
- **Értesítő szolgáltatás** (nem kötelező): pl. `notify.mobile_app_telefonom`. Ha megadod, az integráció maga küldi az értesítést, automatizálás nélkül.

### Entitások

| Entitás | Mit mutat |
| --- | --- |
| `sensor.…_kovetkezo_szallitas` | A következő szállítás napja. Tulajdonságai: `types_text`, `mixed`, `days_until`, `moved`, `upcoming` (a következő 6 szállítás). |
| `sensor.…_kovetkezo_vegyes_szallitas` | Mikor viszik legközelebb a vegyes háztartási hulladékot. |
| `sensor.…_napok_a_szallitasig` | **Visszaszámlálás**: hány nap van hátra (0 = ma). `days_until_mixed`: napok a következő vegyes szállításig. |
| `sensor.…_mit_kell_kitenni` | „Vegyes, szelektív és lebomló” vagy „Szelektív és lebomló”. |
| `binary_sensor.…_holnap_szemetszallitas` | Be van kapcsolva a szállítás előtti napon. |
| `calendar.…_szemetszallitas` | Minden szállítás egész napos eseményként, plusz a szelektív és elektronikai hulladékgyűjtő napok. |

Az emlékeztető időpontjában, ha másnap szállítás van, a Home Assistant egy `gospcom_waste_reminder` eseményt is küld (`message`, `title`, `date`, `types`, `mixed`, `moved`), amire saját automatizálást lehet építeni (pl. Telegram, hangbemondás).

### Kártya példa

```yaml
type: entities
title: 🗑️ Szemétszállítás
entities:
  - entity: sensor.gosp_com_patak_utca_napok_a_szallitasig
    name: Napok a szállításig
  - entity: sensor.gosp_com_patak_utca_mit_kell_kitenni
    name: Mit kell kitenni
  - entity: sensor.gosp_com_patak_utca_kovetkezo_szallitas
    name: Következő szállítás
  - entity: sensor.gosp_com_patak_utca_kovetkezo_vegyes_szallitas
    name: Következő vegyes
```

### Évenkénti frissítés

A menetrend évenként külön fájlban van (`2026.json`, `2027.json`, …). Minden hetet a saját évének fájlja szerint számol, így az új év fájlja már decemberben a helyére kerülhet: január előtt semmit nem változtat, utána pedig a korábbi évek is visszanézhetők a naptárban.

- Amikor a Gosp-Com kiadja a következő évi programot, új verzió jön a HACS-ban.
- Ha addig nem akarsz várni: tedd a fájlt a Home Assistant `config/gospcom_waste/` mappájába (pl. `config/gospcom_waste/2027.json`), és indítsd újra a Home Assistantot. Az itt lévő fájl felülírja a beépített, azonos évűt, és a HACS-frissítés sem törli.

Az adat utáni napokra nem mutat szállítást (`data_until` tulajdonság).

---

## Română

Când și ce deșeuri se colectează pe strada ta în **Târgu Secuiesc, Lunga, Săsăuși și Tinoasa** (Gosp-Com SRL): numărătoare inversă până la următoarea colectare, memento seara cu ce trebuie scos și calendar pentru tot anul. Nu necesită internet sau cont; programul este inclus, după [programul oficial Gosp-Com](https://www.gosp-com.ro/ro/colectare-deseuri-targu-secuiesc-lunga-sasausi-tinoasa).

Regula (2026): în fiecare săptămână, în ziua străzii, se colectează deșeurile **selective și biodegradabile**; în săptămânile impare (galbene în program) și cele **menajere**. Dacă ziua cade într-o sărbătoare legală, colectarea se face în **următoarea zi lucrătoare**.

Instalare: HACS → Custom repositories → `https://github.com/lehel67/ha-gospcom-waste` (Integration), apoi **Setări → Dispozitive și servicii → Adaugă integrare → Gosp-Com**. Străzile apar în română și maghiară.

---

## English

Waste collection of Gosp-Com SRL in **Târgu Secuiesc (Kézdivásárhely), Lunga, Săsăuși and Tinoasa**: next collection, a countdown, what to put out, an evening reminder (event and optional notify service) and a calendar. Works offline; the 2026 schedule is bundled. Selective and biodegradable waste every week on the street's day, mixed household waste every other week (odd ISO weeks), moved to the next working day on Romanian public holidays.

---

*Nem hivatalos, közösségi projekt, nincs kapcsolatban a Gosp-Com SRL-lel. / Proiect neoficial, neafiliat cu Gosp-Com SRL. / Unofficial project, not affiliated with Gosp-Com SRL.*

*A kód nagy részét Claude (Anthropic) segítségével írtuk. / Developed with the help of Claude (Anthropic).*
