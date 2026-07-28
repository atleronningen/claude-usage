# Backlog

Ideer til videreutvikling som ikke er prioritert ennå. Ingen
tidsplan — plukkes opp ved anledning.

## Burn-rate-/proaktivt varsel

Varsle basert på forbrukstakt («på dette tempoet går du tom før
nullstilling») i stedet for en statisk terskel. Differensierer seg fra
den fjernede 90 %-varslingen (se `CHANGELOG.md` / commit `e723fd6`) ved
å være prediktiv i stedet for en ren terskel-ping.

**Kjent komplikasjon:** Anthropic kjører tidsbegrensede promoer som
midlertidig hever ukentlige grenser. `usage_client.py` eksponerer kun
den ferdigberegnede prosenten, ikke selve grenseverdien eller om en
promo er aktiv — så en prosentendring kan skyldes enten mer forbruk
eller en endret grense, uten at appen kan skille dem. Naiv
ekstrapolering vil derfor gi falske utslag rundt hver promo-overgang.

Mulige retninger:
- Drop helt til fordel for historikk/trend-graf under.
- Forenklet variant: kort glidende vindu for takt-beregning, med en
  tydelig «beregner på nytt»-tilstand rett etter et hopp i %, i stedet
  for å vise en prognose man ikke kan stole på.

## Historikk/trend-graf

Lagre målinger lokalt (enkel JSON/SQLite) og vise en sparkline over
siste dager/uke i dropdown-menyen. Viser rådata uten å forsøke å
forutsi noe — rammes ikke av samme falske-varsel-problem som over.

## Snarvei til claude.ai/usage

Klikkbart menypunkt som åpner `claude.ai/settings/usage` direkte i
nettleseren. Lav kompleksitet.

## Konfigurerbar terskel/oppdateringsintervall

`THRESHOLD_PERCENT` (90) og `REFRESH_INTERVAL_SECONDS` (60) er i dag
hardkodet i `main.py`. Gjøre dem innstillbare, f.eks. via `.env` eller
en enkel innstillings-meny.

## Automatisk cookie-fornyelse

Lese cookien direkte fra Chrome i stedet for manuell copy-paste hver
gang den utløper. Større kompleksitet og personvernimplikasjoner —
usikkert verdi/risiko-forhold.

## Per-modell-fordeling

Undersøke om usage-API-et faktisk eksponerer Opus/Sonnet-spesifikke
grenser utover `five_hour`/`seven_day`. Uklart om dette finnes i
responsen slik den er i dag — krever research først.
