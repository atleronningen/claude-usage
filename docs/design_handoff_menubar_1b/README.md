# Handoff: Claude Usage — menylinje-UI «ren tekst, skarpere» (forslag 1b)

## Overview
Claude Usage er en macOS-menylinje-app (`rumps` / `NSStatusItem`) som viser hvor
mye av Claude.ai-abonnementet som er brukt: session-grensen (5 timer) og den
ukentlige grensen, oppdatert hvert 60. sekund.

I dag bor all informasjon i menylinjetittelen (`S:40% U:15%`), og dropdown-menyen
inneholder ingen data — bare en «Ingen feil»-linje og handlinger. Denne
oppgraderingen flytter forbruksdata inn i menyen som lesbare tekstmålere, legger
til nullstillingstidspunkt med nedtelling, korter ned menylinjetittelen, og gjør
feiltilstanden tydeligere.

Valgt retning er bevisst den mest konservative av tre: **alt gjøres med vanlige
`rumps.MenuItem`-strenger**. Ingen `NSAttributedString`, ingen tegnede ikoner,
ingen custom `NSView`, ingen nye avhengigheter. Mørk modus kommer gratis fordi
macOS tegner all tekst selv.

## About the Design Files
Filene i denne pakken er **designreferanser laget i HTML** — mockups som viser
hvordan sluttresultatet skal se ut og oppføre seg. De er ikke produksjonskode og
skal ikke kopieres inn i appen.

Målplattformen er Python + `rumps`. Det HTML-mockupen viser som «grå tekst»,
«skillelinje» og «checkmark» er alt native macOS-menyelementer: oppgaven er å
produsere de riktige **strengene** og de riktige `MenuItem`-tilstandene
(`callback=None` for deaktivert, `state` for avkryssing, `None` for separator),
ikke å gjenskape farger og piksler. Alle piksel-verdier i mockupen er kun for å
gjøre mockupen lesbar (den er vist ~1,6× av faktisk størrelse) — macOS eier
typografi, farger, høyder og marger i en NSMenu.

## Fidelity
**Hi-fi på innhold, ikke på piksler.** Tekststrenger, rekkefølge, gruppering,
separator-plassering, tidsformater og tilstands-oppførsel er endelige og skal
implementeres eksakt som beskrevet under. Visuell styling er utenfor appens
kontroll og skal ikke forsøkes overstyrt.

## Screens / Views

### 1. Menylinjetittel (`NSStatusItem` title)
**Purpose:** gi et blikk-svar på «hvor nær er jeg grensen?» uten å åpne menyen.

| Tilstand | Tittel | Merknad |
|---|---|---|
| Normal | `43 · 76` | sesjon · uke, uten `%` |
| En grense ≥ 90 % | `43 · 92!` | `!` bak den prosenten som har passert |
| Begge ≥ 90 % | `91! · 92!` | |
| Feil | `⚠️` | uendret fra i dag |
| Før første hent | `…` | uendret fra i dag |

Regler:
- Alltid to tall, sesjon først.
- Separator er `" · "` (U+00B7 med mellomrom på hver side).
- Ingen `%`-tegn — kontekst gis i menyen. Dette er hovedgrunnen til at tittelen
  krymper fra 11 til 7–9 tegn.
- Ingen farger og ingen ikoner: tittelen skal se riktig ut i lys og mørk
  menylinje, og bredden skal være stabil så nabo-ikonene ikke hopper.

### 2. Dropdown-meny — normaltilstand
**Purpose:** detaljene — hvor mye av hver grense som er brukt, og når den
nullstilles.

```
Sesjon  ▰▰▰▰▱▱▱▱▱▱ 43%             (deaktivert)
Nullstilles 14:20 (om 1 t 47 min)  (deaktivert)
─────────────────────
Uke     ▰▰▰▰▰▰▰▰▱▱ 76%             (deaktivert)
Nullstilles man 09:00 (om 3 d)     (deaktivert)
─────────────────────
Oppdater nå                        (klikkbar)
✓ Varsle ved 90%                   (av/på, state)
─────────────────────
Avinstaller                        (klikkbar)
Avslutt                            (quit_button)
─────────────────────
v0.1.0 · oppdatert 14:03           (deaktivert)
```

Endringer mot dagens meny:
- Fire nye datalinjer øverst.
- «Ingen feil»-linjen **fjernes helt** i normaltilstand — fravær av feil trenger
  ingen linje. Ved feil settes feilmeldingen inn som øverste element (§3).
- Tidspunkt for siste hent flyttes ned på versjonslinjen.
- «Oppdater nå», «Varsle ved 90%», «Avinstaller», «Avslutt» og versjonsnummeret
  beholder dagens tekst og oppførsel uendret.

#### Målerne (tekststolpene)
- 10 celler. Fylt: `▰` (U+25B0 BLACK PARALLELOGRAM). Tom: `▱` (U+25B1).
- `filled = max(0, min(10, round(percent / 10)))`.
- Etiketten padda til fast bredde slik at begge stolpene starter i samme kolonne:
  `f"{label:<7}{bar} {percent}%"`, `label ∈ {"Sesjon", "Uke"}`.
- Bruk mellomrom, aldri tab. Hele strengen må ligge i samme `MenuItem` for at
  kolonnene skal stemme. NSMenu bruker en proporsjonal systemskrift, så
  kolonnene blir tilnærmet — ikke matematisk — like. Det er akseptabelt; ikke
  bytt til `NSAttributedString` med monospace for å fikse det (utenfor scope).
- Ved ≥ 90 % legges `!` etter prosenten også her: `Uke     ▰▰▰▰▰▰▰▰▰▱ 92%!`

#### Nullstillingslinjene
Format: `Nullstilles {klokke} ({relativ})`

| Avstand til nullstilling | Klokke | Relativ |
|---|---|---|
| < 1 min | `14:20` | `nå` |
| < 1 time | `14:20` | `om 12 min` |
| < 24 timer | `14:20` | `om 1 t 47 min` |
| ≥ 24 timer | `man 09:00` | `om 3 d` |

- Ukedagsforkortelser: `man tir ons tor fre lør søn`.
- Klokke i 24-timers format, lokal tid.
- Relativ tid regnes ut ved **hvert refresh** (hvert 60. sekund), ikke bare ved
  hver henting — nedtellingen skal bevege seg selv om API-svaret er
  mellomlagret.
- Mangler tidspunktet: linjen utelates helt. Aldri en tom eller halv linje.

### 3. Dropdown-meny — feiltilstand
```
Cookien utløpt – oppdater                (klikkbar hvis handlingsbar)
Klikk for oppskrift · siste tall 13:03   (deaktivert)
─────────────────────
Sesjon  ▰▰▰▰▱▱▱▱▱▱ 43%                   (deaktivert)
Uke     ▰▰▰▰▰▰▰▰▱▱ 76%                   (deaktivert)
─────────────────────
Oppdater nå
… resten uendret …
v0.1.0 · oppdatert 13:03
```
- Feilmeldingen ligger øverst, med dagens tekster fra `_show_error`
  (`"Cookien utløpt – oppdater"`, `str(CredentialsMissingError)`,
  `"Uventet feil: …"`), og er klikkbar **kun** når feilen er handlingsbar —
  samme logikk som i dag (`set_callback(self._show_help if actionable else None)`).
- Hjelpelinjen under: `Klikk for oppskrift · siste tall 13:03` når handlingsbar,
  ellers bare `siste tall 13:03`.
- Datalinjene beholdes med siste kjente verdier, men **uten**
  nullstillingslinjer — det er signalet om at tallene er gamle.
- Har appen aldri hentet data: ingen datalinjer i det hele tatt, bare
  feilmelding + hjelpelinje.

## Interactions & Behavior
- **Refresh:** `rumps.Timer` hvert 60. sekund (uendret) → henter data, oppdaterer
  alle `title`-strenger.
- **Oppdater nå:** henter umiddelbart, som i dag.
- **Varsle ved 90%:** uendret toggle som lagrer til `~/.claude-usage/config.json`.
- **Terskelvarsel:** uendret `ThresholdNotifier` ved 90 %. `!`-markeringen i
  tittelen skal bruke **samme terskel** som notifikasjonen — les konstanten fra
  `notifier.py` i stedet for å hardkode 90 to steder.
- **Avinstaller / Avslutt / hjelpe-dialog:** helt uendret.
- Ingen animasjoner, hover-states eller responsivt oppsett — NSMenu eier dette.

## State Management
Utvid `UsageData` i `claude_usage/usage_client.py`:

```python
@dataclass(frozen=True)
class UsageData:
    session_percent: int
    weekly_percent: int
    session_resets_at: datetime | None
    weekly_resets_at: datetime | None
```

- `_parse_usage` leser tidspunktene fra `data["five_hour"]` og
  `data["seven_day"]`. **Verifiser feltnavnet mot en faktisk API-respons** før du
  stoler på det (sannsynligvis `resets_at`, ISO-8601 i UTC). Mangler eller
  ugyldig felt → `None`, aldri en `KeyError` som velter hele hentingen.
- `ClaudeUsageApp` må huske siste vellykkede `UsageData` og tidspunktet for den
  (`self._last_usage`, `self._last_updated_at`) så feiltilstanden kan vise gamle
  tall.
- Menyen bygges **én gang** i `__init__`; `refresh` oppdaterer bare `title` på
  eksisterende `MenuItem`-er. Ikke bygg menyen på nytt — det får menyen til å
  lukke seg om brukeren har den åpen.
- Datalinjer som ikke skal vises, skjules med `menu_item.hidden = True` hvis
  tilgjengelig i din rumps-versjon; ellers hold dem i menyen og sett `title` til
  tom streng er **ikke** akseptabelt — bygg i så fall om den øverste seksjonen
  eksplisitt.

## Code Structure
Legg formateringen i rene funksjoner (ingen `self`, ingen I/O) — de er hele
testflaten:

```python
def format_title(session: int, weekly: int, threshold: int) -> str
def format_meter(label: str, percent: int, threshold: int) -> str
def format_reset(resets_at: datetime | None, now: datetime) -> str | None
def format_footer(version: str, updated_at: datetime | None) -> str
```

Tester i `tests/test_main.py`, parametrisert:
- prosenter: 0, 4, 5, 43, 89, 90, 100, og verdier over 100 (skal klippes til 10 celler)
- nullstilling: `None`, 0 min, 47 min, 1 t 47 min, 3 dager, tidspunkt i fortiden
- tittel: normal, én over terskel, begge over terskel

## Design Tokens
Ingen. Appen har ingen egen visuell flate — farger, skrift, høyder og marger
eies av macOS. De eneste «tokens» i designet er tegn og formater:

| Token | Verdi |
|---|---|
| Fylt målercelle | `▰` U+25B0 |
| Tom målercelle | `▱` U+25B1 |
| Antall celler | 10 |
| Tittelseparator | `" · "` U+00B7 |
| Metaseparator i menyen | `" · "` |
| Terskelmarkør | `!` |
| Feil-tittel | `⚠️` |
| Etikettbredde i måler | 7 tegn |

## Assets
Ingen nye. Menylinjen forblir ren tekst. Det eksisterende, genererte app-ikonet i
`scripts/assets/claude-usage.icns` og `~/Applications/Claude Usage.app` er
uberørt.

## Files in this bundle
- `Claude Usage UI-forslag.dc.html` — HTML-mockup. Turn 1 (nederst) viser dagens
  UI (`1a`) og de tre vurderte retningene (`1b` valgt, `1c` og `1d` forkastet
  som utenfor scope nå). Turn 2 (øverst) viser den valgte retningen i alle
  tilstander: terskel nådd (`2a`), utløpt cookie (`2b`), mørk modus (`2c`).
- `1b-implementasjonsspek.md` — kortversjonen av samme spek, praktisk å ha åpen
  ved siden av koden.
- `screenshots/2a-terskel-naadd.png` — valgt design, en grense over 90 %.
- `screenshots/2b-utloept-cookie.png` — valgt design, feiltilstand.
- `screenshots/2c-moerk-modus.png` — valgt design i mørk modus.

  Skjermbildene er av **turn 2** (det valgte designet). Merk at de er vist ~1,6×
  av faktisk størrelse, og at farger/marger/skrift i bildene er macOS-etterlikning
  for lesbarhet — det som skal implementeres er strengene og
  menyelement-tilstandene, ikke pikslene.

## Files to change in the app
- `claude_usage/usage_client.py` — utvid `UsageData` + `_parse_usage`.
- `claude_usage/main.py` — nye menyelementer, formateringsfunksjoner, ny
  `refresh`/`_show_error`-logikk, ny tittel.
- `tests/test_usage_client.py` — parsing av nullstillingstidspunkt, inkl. manglende felt.
- `tests/test_main.py` — formateringsfunksjonene.
- `README.md` + `CHANGELOG.md` — oppdater eksempelet `S:40% U:15%` og beskriv den
  nye menyen.

## Out of scope
Farget tekst (`NSAttributedString`), tegnet menylinjeikon (`NSImage`), grafisk
panel i menyen (`NSMenuItem.setView_`), historikk/graf over tid, og signering av
appen. Se `1c` og `1d` i mockupen hvis dette blir aktuelt senere.
