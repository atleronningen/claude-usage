# Changelog

Alle vesentlige endringer i dette prosjektet dokumenteres i denne filen.

Formatet følger [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
og prosjektet følger [semantisk versjonering](https://semver.org/lang/nb/).

## [Unreleased]

### Fixed
- Appen dukket opp som et eget "Python"-ikon i Dock/app-switcher fordi
  LaunchAgenten starter venv-pythonen direkte i stedet for via
  app-bundlen. Setter nå aktiveringspolicy til accessory programmatisk
  i `main.py`, uavhengig av hvordan prosessen startes

## [0.2.1] - 2026-07-26

### Changed
- Feilmeldinger som «Uventet HTTP-status: 400» er nå klikkbare og åpner
  samme oppskrift som ved utløpt cookie, i stedet for å være en blindvei
- Oppskriften (README og app-hjelpen) forklarer nå også hvordan
  `CLAUDE_USAGE_API_URL` hentes (feltet **Request URL** i DevTools), ikke
  bare cookien
- README og CLAUDE.md dokumenterer nå at `./install` må kjøres på nytt
  etter å ha flyttet prosjektmappen, siden LaunchAgenten har den
  absolutte stien hardkodet

## [0.2.0] - 2026-07-25

### Added
- MIT-lisens
- App-ikon i `~/Applications` (installert automatisk av `./install`) for å
  starte appen på nytt uten terminal hvis den forsvinner fra menylinjen

### Changed
- README oppdatert til å reflektere at appen kan installeres av andre enn
  Atle, ikke bare til rent personlig bruk
- Menylinjetittel forkortet til `sesjon · uke` (uten `%`), med `!`-markør
  ved ≥ 90 % — se `docs/design_handoff_menubar_1b/`
- Dropdown-menyen viser nå sesjon- og ukeforbruk som tekstmålere med
  nullstillingstidspunkt, i stedet for kun i menylinjetittelen
- Feiltilstanden viser siste kjente tall (uten nullstillingstidspunkt) i
  stedet for å skjule dem helt
- Footeren viser nå tidspunkt for siste vellykkede oppdatering sammen med
  versjonsnummeret (`Oppdatert 14:03 · App v0.1.0`)

### Removed
- «Oppdater nå»-menyvalget (appen oppdaterer seg selv hvert 60. sekund)
- «Varsle ved 90%»-varslingen — samme terskel vises allerede tydelig andre
  steder (`!`-markør i tittel og målere), så en egen push-notifikasjon var
  overflødig

## [0.1.0] - 2026-07-25

### Added
- Menylinje-visning av session- og ukeforbruk, oppdatert hvert minutt
- Varsling ved 90 % forbruk (av/på-bryter)
- LaunchAgent-autostart ved pålogging
- Avinstaller-funksjon (fjerner LaunchAgent og lagrede innstillinger)
- Automatisk installasjonsscript (`./install`)
