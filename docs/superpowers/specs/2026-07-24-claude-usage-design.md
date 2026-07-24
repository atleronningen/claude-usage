# Claude Usage — design

Dato: 2026-07-24

Mappenavn i Playground: `claude-usage`.

## Formål

En macOS-menylinje-app som viser Atles forbruk av Claude.ai-abonnementet
(Pro/Max) i sanntid: hvor mye av "current session"-grensen (5-timer) og
den ukentlige grensen som er brukt opp. Claude Code CLI-en er logget inn
med samme abonnement, så én datakilde dekker begge bruksmåtene — det
trengs ingen separat lesing av lokale Claude Code-logger eller en
Anthropic Admin API-nøkkel.

Til personlig bruk, kjøres kun lokalt på Atles Mac, publiseres ikke.

## Datakilde

`claude.ai/settings/usage`-siden har et internt (udokumentert) API-kall
som henter forbrukstallene. Det er ikke et offisielt/stabilt API — det
kan endre seg uten varsel fra Anthropic.

**Autentisering:** sesjonscookie hentet manuelt fra nettleserens
DevTools (Network-fane → "usage"-forespørselen → Cookie-header) og limt
inn i en lokal `.env`-fil. Cookien utløper med jevne mellomrom og må da
oppdateres manuelt av Atle.

**Kjent risiko:** det nøyaktige JSON-responsformatet er ukjent før et
faktisk svar er hentet og inspisert — dette avklares som første steg i
implementasjonen, ikke i designfasen.

## Arkitektur

- **Språk/rammeverk:** Python med [`rumps`](https://github.com/jaredks/rumps)
  for menylinje-UI-en (valgt fremfor Swift/Electron: raskest å bygge og
  vedlikeholde for et lite personlig verktøy, ingen ny språklæring
  nødvendig, ingen distribusjons-/signeringsbehov som ville favorisert
  Swift).
- **Polling:** en `rumps.Timer` henter data med et konfigurerbart
  intervall (default 5 minutter).
- **Autostart:** en macOS LaunchAgent (`.plist` i
  `~/Library/LaunchAgents/`) starter appen i bakgrunnen ved pålogging.
  Dette er standardmåten å autostarte en ikke-pakket/usignert
  Python-menylinje-app på macOS.

## Komponenter

| Fil | Ansvar |
|---|---|
| `main.py` | `rumps.App`-subklasse. Menylinjetittel, dropdown-meny (Oppdater nå / Innstillinger / Avslutt), timer. |
| `usage_client.py` | Henter og parser usage-responsen. Returnerer session-% og uke-%, eller kaster et eget unntak ved feil. |
| `config.py` | Leser cookie fra `.env`. Leser/skriver innstillinger (oppdateringsintervall, varsling på/av) til `~/.claude-status/config.json`. |
| `notifier.py` | Sender macOS-notifikasjon ved ≥ 90 % forbruk. Holder styr på om varsel allerede er sendt for gjeldende periode, for å unngå gjentatte varsler. |

## Dataflyt

1. Timer fyres.
2. `usage_client.fetch()` henter og parser usage-data.
3. **Ved suksess:** menylinjetittel oppdateres til f.eks. `"S:40% U:15%"`
   (session-% og uke-% vist side ved side, alltid begge synlige samtidig).
   Hvis en av verdiene ≥ 90 % og varsling er slått på og periode ikke
   allerede varslet: send macOS-notifikasjon via `notifier.py`.
4. **Ved feil** (utløpt cookie, nettverksfeil, endepunkt endret format):
   menylinjetittel blir `"?"`. Dropdown-menyen viser en feilmelding med
   påminnelse om å oppdatere cookien i `.env`. Det vises aldri en gammel
   verdi som om den var gyldig — feiltilstand skal alltid være synlig.

## Innstillinger

Tilgjengelig via undermeny i menylinjen, lagres til
`~/.claude-status/config.json`, trer i kraft umiddelbart:

- **Oppdateringsintervall:** 1 / 5 (default) / 15 minutter. Endring
  restarter timeren med nytt intervall.
- **Varsling ved 90 %:** av/på (default: på).

## Testing

- **Unit-tester (pytest):**
  - `usage_client`-parsing mot mocket JSON-svar (gyldig respons, og
    feilrespons som skal gi riktig unntak).
  - Varslingslogikk: skal ikke varsle to ganger for samme periode.
- **Manuell test:** selve menylinje-UI-en (ikon, tekst, dropdown) og
  LaunchAgent-autostart lar seg ikke automatisere og verifiseres
  manuelt etter implementasjon.

## Eksplisitt utenfor scope

- Claude API-forbruk via Anthropic Admin API (krever Admin API-nøkkel
  som ikke er tilgjengelig).
- Lokal parsing av Claude Code-transcript-logger (unødvendig, siden
  claude.ai/settings/usage allerede dekker CLI-bruken).
- Kostnadsestimat i kr/$ (kun prosentandel av grenser vises).
- Distribusjon/signering av appen for andre brukere.
