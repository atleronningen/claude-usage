# Skjermbilde i README.md Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bytt ut tekstboksen i README.md med et ekte skjermbilde av
dropdown-menyen i normaltilstand, og etabler en fast rutine for å
holde skjermbildet oppdatert.

**Architecture:** Rent dokumentasjonsarbeid — ingen kode endres.
Atle tar skjermbildet manuelt og limer det inn i chatten; Claude
kopierer filen til `docs/screenshots/menylinje.png` og oppdaterer
README.md til å referere til den. CLAUDE.md får en ny instruks som
minner Claude om å be om et nytt skjermbilde ved fremtidige
UI-endringer.

**Tech Stack:** Markdown, git. Ingen nye avhengigheter.

## Global Constraints

- Kun normaltilstand fanges i denne omgangen (spec: «Avgrensning») —
  ikke advarsel/feiltilstand eller mørk modus.
- Skjermbildet skal være et ekte skjermbilde av kjørende app
  (v0.2.0), ikke en mockup (spec §2).
- Ingen automatisert skjermbilde-fangst (AppleScript/osascript) —
  bevisst valgt bort (spec «Avgrensning»).
- Endrer ikke de eksisterende bildene i
  `docs/design_handoff_menubar_1b/` (spec «Avgrensning»).
- CHANGELOG.md-oppføringer legges under `## [Unreleased]`, jf.
  `CLAUDE.md`-konvensjonen i prosjektet.

---

### Task 1: Fast rutine i CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (prosjektroten, ikke `.claude/`-varianten)

**Interfaces:**
- Produces: en ny instruks i `CLAUDE.md` som fremtidige Claude-økter
  leser automatisk (ingen kode-grensesnitt).

- [ ] **Step 1: Les gjeldende CLAUDE.md for å finne riktig sted å sette inn instruksen**

Filen har i dag seksjonene `## Stack`, `## Kommandoer`, `## Struktur`,
`## Versjonering`. Sett inn en ny seksjon `## Skjermbilde ved
UI-endringer` etter `## Versjonering`, sist i filen.

- [ ] **Step 2: Legg til seksjonen**

Sett inn følgende tekst nederst i `CLAUDE.md`:

```markdown

## Skjermbilde ved UI-endringer

`README.md` viser et ekte skjermbilde av dropdown-menyen i
normaltilstand: `docs/screenshots/menylinje.png`.

Når en endring påvirker hvordan menylinjen eller dropdown-menyen ser
ut, skal Claude som siste steg før commit minne Atle på å ta et nytt
skjermbilde:

1. Kjør appen og åpne dropdown-menyen i normaltilstand
2. Ta skjermbilde med `⌘+⇧+4` → mellomrom → klikk på vinduet
3. Lim bildet inn i chatten
4. Claude kopierer filen til `docs/screenshots/menylinje.png` med `cp`
```

- [ ] **Step 3: Verifiser at filen er gyldig markdown og at seksjonen kom på rett sted**

Les filen på nytt (f.eks. med `cat CLAUDE.md` eller tilsvarende) og
bekreft at den nye seksjonen ligger etter `## Versjonering` og at
ingen eksisterende innhold ble skadet.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "Legg til rutine for å oppdatere README-skjermbilde ved UI-endringer"
```

---

### Task 2: Skjermbilde og README-oppdatering

**Files:**
- Create: `docs/screenshots/menylinje.png` (kopiert fra bilde limt
  inn av Atle i chatten)
- Modify: `README.md:9-11`
- Modify: `CHANGELOG.md` (seksjon `## [Unreleased]`)

**Interfaces:**
- Consumes: ingenting fra Task 1 (uavhengig endring, kan gjøres i
  hvilken som helst rekkefølge, men følger naturlig etter siden
  rutinen fra Task 1 beskriver nøyaktig denne flyten).
- Produces: `docs/screenshots/menylinje.png` — stien README.md
  refererer til.

**Merk:** Dette steget krever interaktiv input fra Atle (han limer
inn et skjermbilde midt i oppgaven). Det egner seg derfor best for
inline-utførelse i denne økten, ikke for en frittstående subagent som
ikke kan vente på og motta brukerinput.

- [ ] **Step 1: Be Atle ta og lime inn skjermbildet**

Be Atle om å:
1. Kjøre appen (`venv/bin/python -m claude_usage.main`, eller bruke
   den som allerede kjører i menylinjen)
2. Åpne dropdown-menyen i normaltilstand (vanlige forbrukstall, ingen
   advarsel)
3. Ta skjermbilde med `⌘+⇧+4` → mellomrom → klikk på dropdown-vinduet
4. Lime bildet inn direkte i chatten

- [ ] **Step 2: Finn filstien til det innlimte bildet**

Når Atle limer inn bildet, refererer meldingen til en lokal filsti
(vist i tool-resultatet/meldingen). Identifiser denne stien — ikke
gjett, bruk den faktiske stien fra meldingen.

- [ ] **Step 3: Opprett målmappe og kopier filen**

```bash
mkdir -p docs/screenshots
cp "<sti til innlimt bilde>" docs/screenshots/menylinje.png
```

- [ ] **Step 4: Verifiser bildet visuelt**

Bruk Read-verktøyet på `docs/screenshots/menylinje.png` og bekreft at
det faktisk viser dropdown-menyen i normaltilstand (ikke et
skjermdump av feil vindu, tomt bilde e.l.).

- [ ] **Step 5: Oppdater README.md**

Erstatt (linje 9–11):

```markdown
​```
43 · 76
​```
```

med:

```markdown
![Claude Usage-menyen i normaltilstand](docs/screenshots/menylinje.png)
```

- [ ] **Step 6: Legg til CHANGELOG-oppføring**

Under `## [Unreleased]` i `CHANGELOG.md`, legg til:

```markdown
## [Unreleased]

### Changed
- README viser nå et ekte skjermbilde av dropdown-menyen i
  normaltilstand i stedet for en tekstboks
```

(Hvis `## [Unreleased]` allerede har en `### Changed`-liste når denne
oppgaven utføres, legg punktet til i den eksisterende listen i stedet
for å lage en ny.)

- [ ] **Step 7: Verifiser README rendrer riktig**

Sjekk at markdown-syntaksen er korrekt (ingen ødelagt bildereferanse)
ved å lese den oppdaterte `README.md` og bekrefte at stien
`docs/screenshots/menylinje.png` stemmer med filen som faktisk ble
opprettet i Step 3.

- [ ] **Step 8: Commit**

```bash
git add docs/screenshots/menylinje.png README.md CHANGELOG.md
git commit -m "Bytt tekstboks i README med ekte skjermbilde av menylinjen"
```
