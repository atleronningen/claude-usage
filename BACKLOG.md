# Backlog

Ideer til videreutvikling som ikke er prioritert ennå. Ingen
tidsplan – plukkes opp ved anledning.

Flere punkter ble berørt av flerkonto-støtten i v0.3.0, og av det vi så i
usage-responsen da jobbkontoen ble koblet til 13. september 2026. Funnene
er notert under de punktene de gjelder.

## Burn-rate-/proaktivt varsel

Varsle basert på forbrukstakt («på dette tempoet går du tom før
nullstilling») i stedet for en statisk terskel. Differensierer seg fra
den fjernede 90 %-varslingen (se `CHANGELOG.md` / commit `e723fd6`) ved
å være prediktiv i stedet for en ren terskel-ping.

**Kjent komplikasjon:** Anthropic kjører tidsbegrensede promoer som
midlertidig hever ukentlige grenser. En prosentendring kan derfor skyldes
enten mer forbruk eller en endret grense, og naiv ekstrapolering vil gi
falske utslag rundt hver promo-overgang.

**Oppdatert 13. september 2026:** premisset for komplikasjonen holder ikke
helt. Responsen inneholder `limit_dollars`, `used_dollars` og
`remaining_dollars` per seksjon, samt en `limits`-liste der hvert element
har `kind`, `percent`, `severity` og `resets_at`. Selve grenseverdien er
altså eksponert – `usage_client.py` leser den bare ikke. Da kan en
grenseendring oppdages direkte i stedet for å gjettes ut fra et hopp i
prosent.

Forbehold: på både Pro- og Team-kontoen er `limit_dollars` `null` for
`five_hour` og `seven_day`. Seksjonen `amber_ladder` hadde derimot
`limit_dollars: 2500`, så feltene fylles ut for enkelte grensetyper.
Hvilke, og under hvilke betingelser, er ikke kartlagt.

Mulige retninger:
- Drop helt til fordel for historikk/trend-graf under.
- Les `limits`-lista og se om `severity` alene er nok til et nyttig varsel,
  uten egen takt-beregning.
- Forenklet variant: kort glidende vindu for takt-beregning, med en
  tydelig «beregner på nytt»-tilstand rett etter et hopp i %.

## Historikk/trend-graf

Lagre målinger lokalt (enkel JSON/SQLite) og vise en sparkline over
siste dager/uke i dropdown-menyen. Viser rådata uten å forsøke å
forutsi noe – rammes ikke av samme falske-varsel-problem som over.

**Større etter v0.3.0:** målinger må lagres per konto, og grafen må vises
per kontoseksjon i menyen. Kontoens `key` fra `.env` er identiteten å lagre
under. Merk at nøkkelen endrer seg hvis brukeren nummererer om blokkene
sine, så historikken bør tåle at en konto forsvinner og dukker opp igjen.

## Snarvei til claude.ai/usage

Klikkbart menypunkt som åpner `claude.ai/settings/usage` direkte i
nettleseren. Lav kompleksitet.

**Kobling til menydesignet:** dette var alternativet som ble vurdert da
målerlinjene ga blå markering uten å være klikkbare (se `CHANGELOG.md`
v0.3.0). Valget falt på egentegnede linjer. Plukkes snarveien opp, kan
målerlinjene i stedet bli klikkbare og åpne usage-siden for sin konto –
da er markeringen sann, og de egentegnede radene i `main.py`
(`make_meter_line()`) kan fjernes.
Med flere kontoer må snarveien uansett vite hvilken konto den gjelder.

## Konfigurerbar terskel/oppdateringsintervall

`THRESHOLD_PERCENT` (90) og `REFRESH_INTERVAL_SECONDS` (60) er i dag
hardkodet i `main.py`. Gjøre dem innstillbare, f.eks. via `.env` eller
en enkel innstillings-meny.

**Åpent spørsmål etter v0.3.0:** skal terskelen gjelde globalt eller per
konto? En jobbkonto med delte grenser og en privat konto kan fortjene ulik
terskel. Oppdateringsintervallet bør derimot forbli globalt, siden det
styrer én felles hentesyklus for alle kontoer.

## Automatisk cookie-fornyelse

Lese cookien direkte fra Chrome i stedet for manuell copy-paste hver
gang den utløper. Større kompleksitet og personvernimplikasjoner –
usikkert verdi/risiko-forhold.

**Verdien har steget etter v0.3.0:** hver konto har sin egen cookie som
utløper for seg, så den manuelle jobben skalerer med antall kontoer. Den
er også mer tungvint enn før, siden claude.ai holder bare én innlogging
per nettleserprofil – cookien til hver konto må hentes fra sin egen
profil. Risikosiden er uendret.

## Per-modell-fordeling

Undersøke om usage-API-et eksponerer Opus/Sonnet-spesifikke grenser utover
`five_hour`/`seven_day`.

**Undersøkt 13. september 2026:** feltene finnes. Responsen har
`seven_day_opus`, `seven_day_sonnet`, `seven_day_breakdown`,
`seven_day_cowork` og `seven_day_oauth_apps`, alle med samme form som
`five_hour`/`seven_day` (`utilization`, `resets_at`, `limit_dollars` m.m.).

Forbehold: alle fem var `null` på både Pro- og Team-kontoen på
undersøkelsestidspunktet. Det gjenstår å finne ut om de fylles ut ved
tyngre bruk, ved bestemte plantyper, eller om de er utfaset. Sjekk
responsen på nytt i en periode med høyt Opus-forbruk før noe bygges.

Responsen inneholder også flere seksjoner med kodenavn (`amber_ladder`,
`nimbus_quill`, `juniper_tide`, `tangelo` m.fl.). De fleste er `null`, og
betydningen er ukjent – de er udokumenterte og kan forsvinne uten varsel.
