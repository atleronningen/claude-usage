# Versjonering — design

Dato: 2026-07-25

## Formål

Atle har mange ideer til videreutvikling av appen. I dag finnes det
ingen versjonering: ingen `pyproject.toml`, ingen `__version__`, ingen
git-tags. Målet er å:

1. Kunne spore hva som er endret fra versjon til versjon (changelog).
2. Kunne rulle tilbake til en tidligere fungerende versjon ved behov.

Rollback skjer via vanlig `git checkout <tag>` + restart av appen —
ingen egen tooling for dette, det holder med git-tags som
angrepspunkt.

## Versjonsformat og lagring

Semantisk versjonering (`MAJOR.MINOR.PATCH`), startpunkt `0.1.0` siden
appen er i aktiv pre-1.0-utvikling.

**Eneste kilde til sannhet:** `__version__` i `claude_usage/__init__.py`.
Prosjektet er ikke pakket (ingen `pyproject.toml`/`setup.py` i dag — det
kjøres fra et venv), så en full pakke-oppsett kun for versjonsnummeret
er unødvendig. `__init__.py` er allerede importeringspunktet for resten
av koden.

Git-tags (`v0.1.0`, `v0.2.0`, …) peker på committen for hver release og
er det som muliggjør rollback.

## Vis versjon i appen

`main.py` får en ny, ikke-klikkbar menylinje nederst i dropdown-menyen
(`callback=None`, samme mønster som `error_item` uten aktiv feil):
`v0.1.0`. Plasseres i en egen seksjon under «Avinstaller», atskilt med
en skillelinje, slik at man kan se hvilken versjon som faktisk kjører
etter en oppdatering eller rollback.

## CHANGELOG.md

Følger [Keep a Changelog](https://keepachangelog.com)-formatet:

```markdown
# Changelog

## [Unreleased]

## [0.1.0] - 2026-07-25

### Added
- Menylinje-visning av session- og ukeforbruk
- Varsling ved 90 % forbruk
- LaunchAgent-autostart
- Avinstaller-funksjon
```

- **`[Unreleased]`** ligger øverst og fylles på fortløpende med punkter
  etter hvert som funksjoner/fikser legges til — enten av Atle direkte,
  eller av Claude når endringer gjøres på Atles vegne i denne mappen.
- **Første versjon (`0.1.0`)** oppsummerer dagens funksjonalitet som
  baseline, siden appen allerede har mye implementert før versjonering
  innføres.
- Ved release flyttes innholdet under `[Unreleased]` til en ny, datert
  seksjon (`[0.2.0] - 2026-08-01`), og `[Unreleased]` tømmes igjen.

## `scripts/release.sh <versjon>`

Bash-script (samme stil som `scripts/install.sh`) som automatiserer
selve release-prosessen. Tar versjonsnummer uten `v`-prefiks, f.eks.
`./scripts/release.sh 0.2.0`.

**Forhåndssjekker (avbryter med feilmelding hvis noen feiler):**
- Arbeidstreet er rent (`git status` uten endringer).
- Står på `main`.
- `main` er oppdatert med `origin/main` (etter `git fetch`).
- `## [Unreleased]` i `CHANGELOG.md` har faktisk innhold (ikke tom
  seksjon).
- Versjonsnummeret er ikke allerede brukt som git-tag.

**Handling:**
1. Flytt innholdet under `## [Unreleased]` til en ny seksjon
   `## [X.Y.Z] - <dagens dato>`, og opprett en tom `## [Unreleased]` på
   nytt øverst.
2. Oppdater `__version__ = "X.Y.Z"` i `claude_usage/__init__.py`.
3. `git add CHANGELOG.md claude_usage/__init__.py && git commit -m "Release vX.Y.Z"`.
4. `git tag vX.Y.Z`.
5. `git push && git push origin vX.Y.Z`.
6. `gh release create vX.Y.Z --title vX.Y.Z --notes "<innholdet i den nye changelog-seksjonen>"`
   (repoet er nå public, så en faktisk GitHub Release opprettes i
   tillegg til changelog-filen).

## Dokumentasjon

Kort avsnitt i `CLAUDE.md` som forklarer arbeidsflyten:
- Legg til punkter under `## [Unreleased]` i `CHANGELOG.md` fortløpende
  når funksjonalitet endres.
- Kjør `./scripts/release.sh X.Y.Z` for å kutte en ny versjon.

## Testing

- Unit-test for at menyen viser riktig versjonsstreng (leser
  `__version__` fra `claude_usage/__init__.py`).
- `release.sh` verifiseres manuelt (kjøres reelt for `0.1.0` som del av
  implementasjonen) — ikke egnet for automatiserte tester siden det
  gjør ekte git/GitHub-operasjoner.

## Eksplisitt utenfor scope

- Automatisk oppdateringsmekanisme i appen (sjekk mot nyeste git-tag
  e.l.) — Atle oppdaterer manuelt via `git pull`.
- Rollback-script — vanlig `git checkout <tag>` er tilstrekkelig.
- Pakking som pip-installerbar pakke (`pyproject.toml`) — unødvendig
  overhead for et personlig verktøy som kjøres fra et venv.
