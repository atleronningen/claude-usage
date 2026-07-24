# Versjonering — implementasjonsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Innføre semantisk versjonering for claude-usage-appen, slik at endringer kan spores i en changelog og man kan rulle tilbake til en tidligere versjon via git-tags.

**Architecture:** `__version__` i `claude_usage/__init__.py` er eneste kilde til sannhet for versjonsnummeret. Den vises i menylinje-dropdownen, spores i git-tags, og dokumenteres i `CHANGELOG.md` (Keep a Changelog-format). `scripts/release.sh` automatiserer selve release-steget: flytter changelog-innhold, bumper versjon, committer, tagger, pusher og oppretter en GitHub Release.

**Tech Stack:** Python 3 (rumps), bash (release-script, samme stil som eksisterende `scripts/*.sh`), git, GitHub CLI (`gh`).

## Global Constraints

- Versjonsformat: semantisk (`MAJOR.MINOR.PATCH`), startpunkt `0.1.0`.
- Eneste kilde til sannhet for versjonsnummeret: `__version__` i `claude_usage/__init__.py` — ingen `pyproject.toml`/`setup.py`.
- Changelog følger [Keep a Changelog](https://keepachangelog.com)-formatet med en `## [Unreleased]`-seksjon øverst.
- Rollback skjer via `git checkout <tag>` — ingen eget rollback-script.
- `scripts/release.sh` skal matche stilen i `scripts/install.sh`: `#!/usr/bin/env bash`, `set -euo pipefail`, resolve `REPO_DIR` og `cd` dit først.
- Repoet (`atleronningen/claude-usage`) er allerede public og `gh` er autentisert i dette miljøet.

---

### Task 1: `__version__`-konstant og visning i menylinjen

**Files:**
- Modify: `claude_usage/__init__.py`
- Modify: `claude_usage/main.py`
- Test: `tests/test_main.py` (ny fil)

**Interfaces:**
- Produces: `claude_usage.__version__` (str, semver-format), brukt av `main.py` og senere av `scripts/release.sh`.
- Produces: `ClaudeUsageApp.version_item` (`rumps.MenuItem`), brukt i menyen.

- [ ] **Step 1: Skriv feilende test**

Opprett `tests/test_main.py`:

```python
from unittest.mock import patch

from claude_usage import __version__
from claude_usage.config import CredentialsMissingError
from claude_usage.main import ClaudeUsageApp


def test_menu_shows_version():
    with patch(
        "claude_usage.main.config.load_credentials",
        side_effect=CredentialsMissingError("mangler"),
    ):
        app = ClaudeUsageApp()

    assert app.version_item.title == f"v{__version__}"
```

Credentials mockes bort slik at testen aldri leser den ekte `.env`-fila eller gjør nettverkskall — `refresh()` fanger `CredentialsMissingError` og går i feilsporet uten å nå `fetch_usage`.

- [ ] **Step 2: Kjør testen og bekreft at den feiler**

Run: `venv/bin/python -m pytest tests/test_main.py -v`
Expected: FAIL — `AttributeError: 'ClaudeUsageApp' object has no attribute 'version_item'` (eller `ImportError` på `__version__`, siden den ikke finnes ennå).

- [ ] **Step 3: Legg til `__version__`**

I `claude_usage/__init__.py` (fila er tom i dag), legg til:

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Vis versjonen i menyen**

I `claude_usage/main.py`, endre importlinjen (linje 7):

```python
from claude_usage import __version__, config
```

Legg til `version_item` sammen med de andre menyelementene (etter `self.uninstall_item = ...`, rundt linje 32):

```python
        self.uninstall_item = rumps.MenuItem("Avinstaller", callback=self._uninstall)
        self.version_item = rumps.MenuItem(f"v{__version__}", callback=None)
```

Legg den til nederst i `self.menu`-lista (linje 34–41), atskilt med en skillelinje:

```python
        self.menu = [
            self.error_item,
            None,
            self.refresh_item,
            self.notifications_item,
            None,
            self.uninstall_item,
            None,
            self.version_item,
        ]
```

- [ ] **Step 5: Kjør testen og bekreft at den passerer**

Run: `venv/bin/python -m pytest tests/test_main.py -v`
Expected: PASS

- [ ] **Step 6: Kjør hele testsuiten**

Run: `venv/bin/python -m pytest`
Expected: Alle tester passerer (ingen regresjon i `test_config.py`, `test_notifier.py`, `test_usage_client.py`).

- [ ] **Step 7: Commit**

```bash
git add claude_usage/__init__.py claude_usage/main.py tests/test_main.py
git commit -m "Legg til versjonsnummer og vis det i menylinjen"
```

---

### Task 2: `CHANGELOG.md` med baseline-innhold

**Files:**
- Create: `CHANGELOG.md`

**Interfaces:**
- Produces: en `## [Unreleased]`-seksjon med innhold som Task 5 (release-kjøringen) flytter til `## [0.1.0]`.

- [ ] **Step 1: Opprett `CHANGELOG.md`**

```markdown
# Changelog

Alle vesentlige endringer i dette prosjektet dokumenteres i denne filen.

Formatet følger [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
og prosjektet følger [semantisk versjonering](https://semver.org/lang/nb/).

## [Unreleased]

### Added
- Menylinje-visning av session- og ukeforbruk, oppdatert hvert minutt
- Varsling ved 90 % forbruk (av/på-bryter)
- LaunchAgent-autostart ved pålogging
- Avinstaller-funksjon (fjerner LaunchAgent og lagrede innstillinger)
- Automatisk installasjonsscript (`./install`)
```

Dette er ikke automatisk testbart — det verifiseres ved at `scripts/release.sh` (Task 3) klarer å lese og prosessere seksjonen i Task 5.

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "Opprett CHANGELOG.md med baseline-innhold under Unreleased"
```

---

### Task 3: `scripts/release.sh`

**Files:**
- Create: `scripts/release.sh`

**Interfaces:**
- Consumes: `CHANGELOG.md` sin `## [Unreleased]`-seksjon (Task 2), `__version__`-linjen i `claude_usage/__init__.py` (Task 1).
- Produces: git-commit "Release vX.Y.Z", git-tag `vX.Y.Z`, push til `origin`, og en GitHub Release via `gh release create`.

- [ ] **Step 1: Opprett scriptet**

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

VERSION="${1:-}"
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Bruk: $0 <versjon, f.eks. 0.2.0>" >&2
    exit 1
fi
TAG="v$VERSION"

if [ -n "$(git status --porcelain)" ]; then
    echo "Feil: arbeidstreet er ikke rent. Committ eller stash endringer først." >&2
    exit 1
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$BRANCH" != "main" ]; then
    echo "Feil: må stå på main (er på $BRANCH)." >&2
    exit 1
fi

echo "Henter siste main fra origin..."
git fetch origin main --quiet
LOCAL="$(git rev-parse main)"
REMOTE="$(git rev-parse origin/main)"
if [ "$LOCAL" != "$REMOTE" ]; then
    echo "Feil: main er ikke oppdatert med origin/main." >&2
    exit 1
fi

if git rev-parse "$TAG" >/dev/null 2>&1; then
    echo "Feil: taggen $TAG finnes allerede." >&2
    exit 1
fi

NOTES_FILE="$(mktemp)"
trap 'rm -f "$NOTES_FILE"' EXIT

python3 - "$VERSION" "$NOTES_FILE" <<'PYEOF'
import re
import sys
from datetime import date

version, notes_path = sys.argv[1], sys.argv[2]

changelog_path = "CHANGELOG.md"
with open(changelog_path) as f:
    content = f.read()

unreleased_heading = "## [Unreleased]"
start = content.find(unreleased_heading)
if start == -1:
    sys.exit("Feil: fant ikke '## [Unreleased]' i CHANGELOG.md")

body_start = start + len(unreleased_heading)
next_heading = content.find("\n## [", body_start)
body = content[body_start:next_heading if next_heading != -1 else len(content)]
body = body.strip("\n")

if not body.strip():
    sys.exit("Feil: '## [Unreleased]' i CHANGELOG.md er tom. Legg til endringer før release.")

today = date.today().isoformat()
new_section = f"{unreleased_heading}\n\n## [{version}] - {today}\n\n{body}\n"

rest = content[next_heading:] if next_heading != -1 else ""
new_content = content[:start] + new_section + ("\n" if rest else "") + rest.lstrip("\n")

with open(changelog_path, "w") as f:
    f.write(new_content)

with open(notes_path, "w") as f:
    f.write(f"## [{version}] - {today}\n\n{body}\n")

init_path = "claude_usage/__init__.py"
with open(init_path) as f:
    init_content = f.read()

new_init_content = re.sub(
    r'^__version__ = ".*"$',
    f'__version__ = "{version}"',
    init_content,
    flags=re.MULTILINE,
)
if new_init_content == init_content:
    sys.exit(f"Feil: fant ikke __version__-linje i {init_path}")

with open(init_path, "w") as f:
    f.write(new_init_content)
PYEOF

git add CHANGELOG.md claude_usage/__init__.py
git commit -m "Release $TAG"
git tag "$TAG"
git push origin main
git push origin "$TAG"
gh release create "$TAG" --title "$TAG" --notes-file "$NOTES_FILE"

echo "Ferdig: $TAG er tagget, pushet og publisert som GitHub Release."
```

- [ ] **Step 2: Gjør scriptet kjørbart**

```bash
chmod +x scripts/release.sh
```

- [ ] **Step 3: Verifiser forhåndssjekkene uten å faktisk kjøre en release**

Run: `./scripts/release.sh` (uten argument)
Expected: Feilmelding `Bruk: ./scripts/release.sh <versjon, f.eks. 0.2.0>` og exit-kode ≠ 0.

Run: `./scripts/release.sh ikke-et-semver`
Expected: Samme bruksmelding, exit-kode ≠ 0.

(Selve happy-path-kjøringen — som faktisk tagger, pusher og oppretter en GitHub Release — skjer i Task 5, som en egen, bevisst handling.)

- [ ] **Step 4: Commit**

```bash
git add scripts/release.sh
git commit -m "Legg til scripts/release.sh for å automatisere versjons-release"
```

---

### Task 4: Dokumenter arbeidsflyten i `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Ingen kode — ren dokumentasjon for fremtidige Claude-økter i dette repoet.

- [ ] **Step 1: Legg til en «Versjonering»-seksjon**

I `CLAUDE.md`, legg til en ny seksjon etter `## Struktur` (til slutt i fila):

```markdown

## Versjonering

Semantisk versjonering (`MAJOR.MINOR.PATCH`). `__version__` i
`claude_usage/__init__.py` er eneste kilde til sannhet, og vises i
menylinjens dropdown-meny.

- Legg til punkter under `## [Unreleased]` i `CHANGELOG.md` fortløpende
  når funksjonalitet legges til, endres eller fjernes.
- Kjør `./scripts/release.sh X.Y.Z` for å kutte en ny versjon. Scriptet
  flytter Unreleased-innholdet til en datert seksjon, bumper
  `__version__`, committer, tagger, pusher og oppretter en GitHub
  Release. Krever rent arbeidstre og at `main` er oppdatert med
  `origin/main`.
- Rollback: `git checkout vX.Y.Z` og restart appen.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "Dokumenter versjonerings-arbeidsflyt i CLAUDE.md"
```

---

### Task 5: Kutt den første releasen (0.1.0)

**Files:**
- Ingen nye filer — kjører `scripts/release.sh` fra Task 3 mot innholdet fra Task 1–2.

**Interfaces:**
- Consumes: `scripts/release.sh` (Task 3), `CHANGELOG.md` (Task 2), `claude_usage/__init__.py` (Task 1).
- Produces: git-tag `v0.1.0` på GitHub, en publisert GitHub Release, og oppdatert `CHANGELOG.md`/`__version__` på `main`.

**OBS:** Dette steget pusher til `origin/main` og oppretter en offentlig GitHub Release. Bekreft med Atle før scriptet kjøres, siden det er en handling som er synlig for andre og ikke uten videre reversibel.

- [ ] **Step 1: Push commits fra Task 1–4**

```bash
git push origin main
```

- [ ] **Step 2: Kjør release-scriptet**

```bash
./scripts/release.sh 0.1.0
```

Expected: Scriptet flytter Unreleased-innholdet til `## [0.1.0] - 2026-07-25` i `CHANGELOG.md`, setter `__version__ = "0.1.0"`, committer, tagger `v0.1.0`, pusher, og oppretter en GitHub Release med changelog-innholdet som notater.

- [ ] **Step 3: Verifiser resultatet**

```bash
git log --oneline -3
git tag
gh release view v0.1.0
```

Expected: Siste commit er `Release v0.1.0`, taggen `v0.1.0` finnes lokalt og på GitHub, og `gh release view v0.1.0` viser den publiserte releasen med riktig changelog-tekst.

- [ ] **Step 4: Verifiser menyen manuelt**

Run: `venv/bin/python -m claude_usage.main`

Åpne dropdown-menyen og bekreft at `v0.1.0` vises nederst. Avslutt appen (`Avslutt` i menyen) når verifisert.

---

## Self-Review

- **Spec-dekning:** Versjonsformat/lagring → Task 1. Vis i UI → Task 1. CHANGELOG-format → Task 2. `release.sh`-atferd (forhåndssjekker + handling) → Task 3, faktisk kjørt → Task 5. Dokumentasjon → Task 4. Testing (unit-test for versjonsstreng, manuell verifisering av release.sh) → Task 1 og Task 5. Alt fra spec er dekket.
- **Placeholder-skann:** Ingen TBD/TODO — alle steg har konkret kode eller konkrete kommandoer.
- **Typekonsistens:** `__version__` (str) importeres likt i `main.py`, testen og `release.sh` sin regex. `version_item`-navnet brukes konsekvent i Task 1 og verifiseres samme sted (ingen senere task refererer til det under et annet navn).
