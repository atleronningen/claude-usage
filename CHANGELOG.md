# Changelog

Alle vesentlige endringer i dette prosjektet dokumenteres i denne filen.

Formatet følger [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
og prosjektet følger [semantisk versjonering](https://semver.org/lang/nb/).

## [Unreleased]

### Added
- MIT-lisens

### Changed
- README oppdatert til å reflektere at appen kan installeres av andre enn
  Atle, ikke bare til rent personlig bruk

## [0.1.0] - 2026-07-25

### Added
- Menylinje-visning av session- og ukeforbruk, oppdatert hvert minutt
- Varsling ved 90 % forbruk (av/på-bryter)
- LaunchAgent-autostart ved pålogging
- Avinstaller-funksjon (fjerner LaunchAgent og lagrede innstillinger)
- Automatisk installasjonsscript (`./install`)
