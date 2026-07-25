# Changelog

Alle vesentlige endringer i dette prosjektet dokumenteres i denne filen.

Formatet følger [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
og prosjektet følger [semantisk versjonering](https://semver.org/lang/nb/).

## [Unreleased]

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
