# Claude Usage — UI-spek for valgt design (1b: «ren tekst, skarpere»)

Handoff til Claude Code CLI. Alt holder seg innenfor `rumps` — ingen PyObjC,
ingen nye avhengigheter.

## 1. Menylinjetittel

| Tilstand | Tittel |
|---|---|
| Normal | `43 · 76` (sesjon · uke, uten `%`) |
| En grense ≥ 90 % | `43 · 92!` (utropstegn bak den som har passert) |
| Feil | `⚠️` (som i dag) |
| Før første hent | `…` (som i dag) |

Regler: alltid to tall, sesjon først, separator `" · "` (mellomrom rundt).
Ingen farger, ingen ikoner — tittelen skal se riktig ut i både lys og mørk
menylinje, og bredden skal være stabil (maks 8 tegn).

## 2. Dropdown-meny, topp til bunn

```
Sesjon  ▰▰▰▰▱▱▱▱▱▱ 43%        (deaktivert)
Nullstilles 14:20 (om 1 t 47 min)   (deaktivert, dempet)
──────────
Uke     ▰▰▰▰▰▰▰▰▱▱ 76%        (deaktivert)
Nullstilles man 09:00 (om 3 d)      (deaktivert, dempet)
──────────
Oppdater nå                          (klikkbar)
✓ Varsle ved 90%                     (av/på)
──────────
Avinstaller
Avslutt
──────────
v0.1.0 · oppdatert 14:03             (deaktivert)
```

Endringer mot dagens meny:
- Fire nye datalinjer øverst (var: kun «Ingen feil»).
- «Ingen feil»-linjen fjernes helt i normaltilstand — fravær av feil trenger
  ingen linje. Ved feil settes feilmeldingen inn som **øverste** element, med
  en hjelpelinje under (se §4).
- Tidspunkt for siste hent flyttes ned til versjonslinjen.

### Målerne
- 10 celler, `▰` (U+25B0) fylt / `▱` (U+25B1) tom.
- `filled = max(0, min(10, round(percent / 10)))`.
- Etiketten padda til fast bredde slik at begge stolpene starter i samme
  kolonne: `f"{label:<7}{bar} {percent}%"` med `label` i `("Sesjon", "Uke")`.
  Hele strengen må rendres i samme skrift for at kolonnene skal stemme —
  bruk mellomrom, ikke tab.
- Ved ≥ 90 %: legg `!` etter prosenten på den linjen også.

### Nullstillingslinjene
- Format: `Nullstilles {klokke} ({relativ})`.
  - Under 24 t: `14:20` + `om 1 t 47 min` / `om 12 min` / `nå`.
  - Over 24 t: `man 09:00` + `om 3 d` (norske forkortelser man–søn).
- Relativ tid regnes ut ved hvert refresh (hvert 60. s), ikke bare ved henting.

## 3. Datakrav

`UsageData` må utvides med nullstillingstidspunkt:

```python
@dataclass(frozen=True)
class UsageData:
    session_percent: int
    weekly_percent: int
    session_resets_at: datetime | None
    weekly_resets_at: datetime | None
```

`_parse_usage` leser dem fra `data["five_hour"]` / `data["seven_day"]`.
**Verifiser feltnavnet mot en faktisk API-respons** (sannsynlig `resets_at`,
ISO-8601 UTC) — hvis feltet mangler eller ikke kan tolkes, skal
nullstillingslinjen utelates helt, ikke vises tom. Ingen `KeyError` som velter
hele hentingen.

## 4. Feiltilstand

- Menylinje: `⚠️`.
- Øverste menyelement: feilmeldingen (samme tekster som i dag), klikkbar kun
  når feilen er handlingsbar — uendret logikk fra `_show_error`.
- Ny linje under: `Klikk for oppskrift · siste tall 13:03` når feilen er
  handlingsbar, ellers bare `siste tall 13:03`.
- Datalinjene beholdes med siste kjente verdier, men uten nullstillingslinjer,
  slik at det er tydelig at tallene er gamle. Første gang appen aldri har
  hentet data: ingen datalinjer.

## 5. Struktur i koden

- Bygg menyen én gang i `__init__` (som i dag) og oppdater bare `title` på
  eksisterende `MenuItem`-er i `refresh` — ikke bygg menyen på nytt.
- Legg formatering i egne, rene funksjoner (lett å teste):
  - `format_title(session, weekly, error=False) -> str`
  - `format_meter(label, percent) -> str`
  - `format_reset(resets_at, now) -> str | None`
- Tester: `tests/test_main.py` utvides med parametriserte tester på de tre
  funksjonene (0 %, 5 %, 43 %, 90 %, 100 %; nullstilling om 0 min / 47 min /
  3 dager / `None`).

## 6. Utenfor scope

Farget tekst (`NSAttributedString`), tegnet menylinjeikon og grafisk panel
(`NSMenuItem.setView_`) er bevisst ikke med — se forslag 1c og 1d i
`Claude Usage UI-forslag.dc.html` hvis det blir aktuelt senere.
