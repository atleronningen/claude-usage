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

if ! gh auth status >/dev/null 2>&1; then
    echo "Feil: ikke logget inn med gh. Kjør 'gh auth login' først." >&2
    exit 1
fi

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

# Step 1: Read all files
changelog_path = "CHANGELOG.md"
with open(changelog_path) as f:
    changelog_content = f.read()

init_path = "claude_usage/__init__.py"
with open(init_path) as f:
    init_content = f.read()

# Step 2: Validate everything before writing anything to disk
unreleased_heading = "## [Unreleased]"
start = changelog_content.find(unreleased_heading)
if start == -1:
    sys.exit("Feil: fant ikke '## [Unreleased]' i CHANGELOG.md")

body_start = start + len(unreleased_heading)
next_heading = changelog_content.find("\n## [", body_start)
body = changelog_content[body_start:next_heading if next_heading != -1 else len(changelog_content)]
body = body.strip("\n")

if not body.strip():
    sys.exit("Feil: '## [Unreleased]' i CHANGELOG.md er tom. Legg til endringer før release.")

# Validate __version__ line exists BEFORE attempting substitution
if not re.search(r'^__version__ = ".*"$', init_content, flags=re.MULTILINE):
    sys.exit(f"Feil: fant ikke __version__-linje i {init_path}")

# Step 3: Compute new content
today = date.today().isoformat()
new_section = f"{unreleased_heading}\n\n## [{version}] - {today}\n\n{body}\n"

rest = changelog_content[next_heading:] if next_heading != -1 else ""
new_changelog_content = changelog_content[:start] + new_section + ("\n" if rest else "") + rest.lstrip("\n")

new_init_content = re.sub(
    r'^__version__ = ".*"$',
    f'__version__ = "{version}"',
    init_content,
    flags=re.MULTILINE,
)

# Step 4: Write all files (all-or-nothing after validation is complete)
with open(changelog_path, "w") as f:
    f.write(new_changelog_content)

with open(notes_path, "w") as f:
    f.write(f"## [{version}] - {today}\n\n{body}\n")

with open(init_path, "w") as f:
    f.write(new_init_content)
PYEOF

git add CHANGELOG.md claude_usage/__init__.py
git commit -m "Release $TAG"
git tag "$TAG"
git push --atomic origin main "$TAG"
gh release create "$TAG" --title "$TAG" --notes-file "$NOTES_FILE"

echo "Ferdig: $TAG er tagget, pushet og publisert som GitHub Release."
