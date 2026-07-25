# Claude Usage

[github.com/atleronningen/claude-usage](https://github.com/atleronningen/claude-usage)

En liten macOS-menylinje-app som viser hvor mye av Claude.ai-abonnementet
(Pro/Max) du har brukt opp — både session-grensen (5 timer) og den
ukentlige grensen, oppdatert hvert minutt.

```
43 · 76
```

Kjøres fra kildekode via et lokalt Python-virtualenv — ikke pakket eller
signert som en frittstående macOS-app.

## Hvordan det virker

Claude Code CLI-en bruker samme innlogging som claude.ai, så begge
bruksmåtene trekker på de samme grensene. Appen leser derfor forbruket
direkte fra det interne (udokumenterte) API-et bak
`claude.ai/settings/usage`, autentisert med en sesjonscookie du henter
manuelt fra nettleseren.

Dette er ikke et offisielt API og kan slutte å virke uten varsel hvis
Anthropic endrer det.

**Cloudflare:** endepunktet er beskyttet av Cloudflares bot-deteksjon,
som blokkerer på TLS-fingerprint uavhengig av om cookien er gyldig.
Appen bruker derfor
[`curl_cffi`](https://github.com/lexiforest/curl_cffi) (som etterligner
Chromes TLS-fingerprint) i stedet for vanlig `requests` — se kommentaren
i `claude_usage/usage_client.py` for detaljer.

## Installasjon

Krever macOS og Python 3.

```bash
git clone https://github.com/atleronningen/claude-usage.git
cd claude-usage
./install
```

`./install` gjør alt: oppretter et virtualenv, installerer
avhengigheter, oppretter en `.env`-fil fra malen, og setter opp en
LaunchAgent som starter appen automatisk ved pålogging.

### Sett opp cookien

Første gang må du selv hente en cookie fra nettleseren din:

1. Åpne `claude.ai/settings/usage`, åpne utviklerverktøy (⌘+⌥+I) →
   Network-fanen
2. Last siden på nytt, klikk på `usage`-forespørselen
3. Under **Headers** → **Request Headers**: kopier hele
   `Cookie`-verdien
4. Lim den inn som `CLAUDE_USAGE_COOKIE` i `.env`-filen (opprettet av
   `./install`)
5. Legg også inn URL-en til selve forespørselen som
   `CLAUDE_USAGE_API_URL` (ser slik ut:
   `https://claude.ai/api/organizations/<org-id>/usage`)

Cookien utløper med jevne mellomrom. Når appen viser ⚠️ i menylinjen,
klikk på feilmeldingen i dropdown-menyen — den åpner `.env` i TextEdit
og viser samme oppskrift som over.

## Bruk

- **Menylinjen** viser sesjon- og uke-forbruk side ved side (f.eks. `43 · 76`),
  med `!` bak et tall som har passert 90 %, eller ⚠️ ved feil (utløpt cookie,
  nettverksfeil e.l.)
- **Dropdown-menyen** viser begge grensene som tekstmålere
  (`Sesjon  ▰▰▰▰▱▱▱▱▱▱ 43%`) med nullstillingstidspunkt under hver, appen
  oppdaterer seg selv hvert minutt
- **Varsle ved 90%** — av/på-bryter for macOS-notifikasjon når en
  grense nærmer seg fullt brukt
- **Avinstaller** — fjerner LaunchAgent-en, app-ikonet og lagrede
  innstillinger (spør om bekreftelse først; selve prosjektmappen og
  `.env` beholdes)

`./install` legger også `Claude Usage.app` i `~/Applications`. Hvis appen
skulle forsvinne fra menylinjen (f.eks. etter «Avslutt»), finner du den
igjen i Launchpad eller Spotlight — et klikk på ikonet starter den på
nytt.

## Utvikling

```bash
venv/bin/pip install -r requirements-dev.txt   # avhengigheter
venv/bin/python -m pytest                      # kjør tester
venv/bin/python -m claude_usage.main           # kjør appen manuelt
```

Se `CLAUDE.md` for mer om stack og mappestruktur, og
`docs/superpowers/` for opprinnelig design-spec og implementasjonsplan.

## Lisens

[MIT](LICENSE).
