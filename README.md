# Claude Usage

[github.com/atleronningen/claude-usage](https://github.com/atleronningen/claude-usage)

En liten macOS-menylinje-app som viser hvor mye av Claude.ai-abonnementet
du har brukt opp — både session-grensen (5 timer) og den ukentlige
grensen, oppdatert hvert minutt. Har du flere kontoer, vises alle i
dropdown-menyen.

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

### Hvis du flytter prosjektmappen

Autostart-oppsettet (LaunchAgenten) har prosjektmappens absolutte sti
hardkodet fra installasjonstidspunktet. Flytter du mappen til et annet sted,
finner appen ikke veien fra `~/Applications`-ikonet lenger. Kjør `./install`
på nytt fra den nye plasseringen for å fikse dette — `.env` ligger i
prosjektmappen og flyttes med, så du trenger ikke hente ny cookie/org-ID.

### Sett opp cookien

Første gang må du selv hente en cookie fra nettleseren din:

1. Åpne `claude.ai/settings/usage`, åpne utviklerverktøy (⌘+⌥+I) →
   Network-fanen
2. Last siden på nytt, klikk på `usage`-forespørselen
3. Under **Headers** → **Request Headers**: kopier hele
   `Cookie`-verdien
4. Lim den inn som `CLAUDE_USAGE_ACCOUNT_1_COOKIE` i `.env`-filen
   (opprettet av `./install`)
5. Under **Headers**: kopier feltet **Request URL** (øverst i panelet)
   og lim den inn som `CLAUDE_USAGE_ACCOUNT_1_API_URL` (ser slik ut:
   `https://claude.ai/api/organizations/<org-id>/usage`)
6. Gi kontoen et navn i `CLAUDE_USAGE_ACCOUNT_1_LABEL` — det vises i
   menyen, så plantypen er et greit valg: `Pro`, `Max`, `Team Plan`

Cookien utløper med jevne mellomrom. Når appen viser ⚠️ i menylinjen,
klikk på feilmeldingen i dropdown-menyen — den åpner `.env` i TextEdit
og viser oppskriften for nettopp den kontoen.

Har du en eldre `.env` med `CLAUDE_USAGE_COOKIE` og
`CLAUDE_USAGE_API_URL` uten nummer, virker den fortsatt som den er —
den tolkes som én konto.

### Flere kontoer

Legg til en blokk per konto, nummerert fortløpende:

```
CLAUDE_USAGE_ACCOUNT_1_LABEL=Pro
CLAUDE_USAGE_ACCOUNT_1_COOKIE=...
CLAUDE_USAGE_ACCOUNT_1_API_URL=https://claude.ai/api/organizations/<org-id>/usage

CLAUDE_USAGE_ACCOUNT_2_LABEL=Team Plan
CLAUDE_USAGE_ACCOUNT_2_COOKIE=...
CLAUDE_USAGE_ACCOUNT_2_API_URL=https://claude.ai/api/organizations/<annen-org-id>/usage
```

Hver konto trenger sin egen cookie, hentet mens du er logget inn som
den kontoen. claude.ai holder bare én innlogging per nettleserprofil,
så bruk to profiler (eller et privat vindu) når du henter den andre.

Alle kontoer hentes hvert minutt, parallelt. Menylinjetittelen viser
den kontoen som er merket med hake i dropdown-menyen — klikk på en
annen konto for å bytte. Valget huskes i `~/.claude-usage/state.json`
og overlever omstart. En utløpt cookie på én konto påvirker ikke de
andre.

## Bruk

- **Menylinjen** viser sesjon- og uke-forbruk for den aktive kontoen side ved
  side (f.eks. `43 · 76`), med `!` bak et tall som har passert 90 %, eller ⚠️
  ved feil (utløpt cookie, nettverksfeil e.l.)
- **Dropdown-menyen** viser begge grensene på hver sin linje, med etikett,
  stolpe, prosent og nedtelling til nullstilling i faste kolonner. Stolpen og
  prosenten blir røde over 90 %, og klokkeslettet for nullstillingen ligger i
  verktøytipset på linjen. Appen oppdaterer seg selv hvert minutt. Med flere
  kontoer får hver konto sin egen seksjon, og den aktive er merket med hake –
  klikk på en annen for å bytte
- **Avinstaller** — fjerner LaunchAgent-en og app-ikonet (spør om
  bekreftelse først; selve prosjektmappen og `.env` beholdes)

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
