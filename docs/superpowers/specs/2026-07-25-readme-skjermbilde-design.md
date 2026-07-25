# Design: Skjermbilde i README.md

## Bakgrunn

README.md viser i dag menylinje-forbruket som en ren tekstboks
(```43 · 76```) i stedet for et faktisk skjermbilde av appen. De
eneste bildene som finnes i prosjektet ligger i
`docs/design_handoff_menubar_1b/screenshots/` og er utdaterte
design-mockups fra v0.1.0 — de viser blant annet «Varsle ved 90%»,
som ble fjernet i v0.2.0 (commit `e723fd6`).

## Løsning

### 1. README.md

Kodeblokken med `43 · 76` (linje 9–11) erstattes med et
markdown-bilde av dropdown-menyen i normaltilstand:

```markdown
![Claude Usage-menyen i normaltilstand](docs/screenshots/menylinje.png)
```

### 2. Skjermbildet

Nytt bilde: `docs/screenshots/menylinje.png` — ekte skjermbilde av
den kjørende appen (v0.2.0), ikke en mockup. Viser kun
normaltilstand (ingen advarsel-/feiltilstand eller mørk modus i
denne omgangen).

Innsamlingsflyt (manuell, gjentas ved fremtidige oppdateringer):

1. Atle kjører appen og åpner dropdown-menyen i normaltilstand
2. Tar skjermbilde med `⌘+⇧+4` → mellomrom → klikk på vinduet
   (utklippstavle eller fil, begge funker)
3. Limer bildet inn direkte i chatten med Claude
4. Claude leser filen chatten refererer til og kopierer den til
   `docs/screenshots/menylinje.png` med `cp`

### 3. Fast rutine (CLAUDE.md)

`CLAUDE.md` i prosjektroten får en kort instruks om at Claude skal
minne Atle på å ta et nytt skjermbilde (samme fremgangsmåte som
over) som siste steg før commit, når en endring påvirker
menylinje- eller dropdown-UI-et. Formålet er å holde
`docs/screenshots/menylinje.png` synkronisert med appens faktiske
utseende over tid.

## Avgrensning

- Kun normaltilstand fanges i denne omgangen — ikke
  advarsel/feiltilstand eller mørk modus.
- Ingen automatisert skjermbilde-fangst (AppleScript/osascript) —
  vurdert og valgt bort til fordel for manuell fangst + chat-lim.
- Endrer ikke de eksisterende design handoff-bildene i
  `docs/design_handoff_menubar_1b/`.
