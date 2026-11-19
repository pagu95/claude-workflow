#!/usr/bin/env bash
# Install this workflow into ~/.claude on the current machine. Safe to re-run.
# - symlinks skills/* into ~/.claude/skills (existing real dirs are moved to a dated backup) and
#   removes the links it left for renamed or deleted skills
# - symlinks profiles/*.md (except TEMPLATE.md) into ~/.claude/profiles
# - with --overlay <dir>: does the same for that private repo's skills/ and profiles/, and links its
#   <dir>/ledger/LESSONS.md to ~/.claude/retro/LESSONS.md, and records <dir> in ~/.claude/claude-workflow-overlay
# - a real profile or ledger file is replaced by a link only when its content is identical to the repo's
# - adds an @import of this repo's CLAUDE.md to ~/.claude/CLAUDE.md (never overwrites the file)
set -euo pipefail

# Git Bash on Windows copies instead of linking unless asked for native symlinks.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) export MSYS=winsymlinks:nativestrict ;;
esac

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
BACKUP="$CLAUDE_DIR/skills.bak-$(date +%Y%m%d-%H%M%S)"

OVERLAY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --overlay) OVERLAY="$(cd "${2:?--overlay needs a path}" && pwd)"; shift 2 ;;
    *) echo "usage: install.sh [--overlay <private repo>]" >&2; exit 2 ;;
  esac
done

mkdir -p "$CLAUDE_DIR/skills" "$CLAUDE_DIR/profiles" "$CLAUDE_DIR/handoffs" "$CLAUDE_DIR/retro"

# Link <root>/skills/* into ~/.claude/skills, then drop the links <root> left for skills that were
# renamed or deleted (e.g. resume -> ckore-resume). Only links into <root>/skills/ that weren't just
# linked go; anything else is left alone.
link_skills() {
  local root="$1" src name dest linked=" "
  for src in "$root"/skills/*/; do
    [ -d "$src" ] || continue
    name="$(basename "$src")"
    # A renamed skill's old folder can survive a pull holding only ignored files (__pycache__).
    [ -n "$(find "$src" -mindepth 1 -maxdepth 1 ! -name __pycache__ -print -quit)" ] || continue
    linked="$linked$name "
    dest="$CLAUDE_DIR/skills/$name"
    if [ -e "$dest" ] && [ ! -L "$dest" ]; then
      mkdir -p "$BACKUP"
      mv "$dest" "$BACKUP/$name"
      echo "backed up $dest -> $BACKUP/$name"
    fi
    ln -sfn "${src%/}" "$dest"
    echo "skill   $name"
  done
  for dest in "$CLAUDE_DIR"/skills/*; do
    [ -L "$dest" ] || continue
    case "$linked" in *" $(basename "$dest") "*) continue ;; esac
    case "$(readlink "$dest")" in
      "$root"/skills/*) rm "$dest"; echo "removed stale link $(basename "$dest")" ;;
    esac
  done
}

# Link one file. A real (non-link) file already there is replaced only when it holds exactly what
# the source holds (the switch-over case: the home copy was moved into the repo); otherwise it stays.
link_file() {
  local src="$1" dest="$2" label="$3"
  if [ "$src" -ef "$dest" ]; then  # already the same file, e.g. ~/.claude/retro links to the repo's folder
    echo "$label"
    return
  fi
  if [ -e "$dest" ] && [ ! -L "$dest" ]; then
    if ! cmp -s "$src" "$dest"; then
      echo "skip    $label: $dest is a real file that differs from $src. Copy it over the repo file (or delete it) and re-run to link."
      return
    fi
    rm "$dest"
  fi
  ln -sfn "$src" "$dest"
  echo "$label"
}

link_profiles() {
  local src name
  for src in "$1"/profiles/*.md; do
    [ -e "$src" ] || continue
    name="$(basename "$src")"
    [ "$name" = "TEMPLATE.md" ] && continue
    link_file "$src" "$CLAUDE_DIR/profiles/$name" "profile $name"
  done
}

link_skills "$REPO"
link_profiles "$REPO"
if [ -n "$OVERLAY" ]; then
  link_skills "$OVERLAY"
  link_profiles "$OVERLAY"
  # Lets the public repo's leak check find the deny list (tests/test_leak_denylist.py).
  echo "$OVERLAY" > "$CLAUDE_DIR/claude-workflow-overlay"
  [ -e "$OVERLAY/ledger/LESSONS.md" ] && link_file "$OVERLAY/ledger/LESSONS.md" "$CLAUDE_DIR/retro/LESSONS.md" "ledger  ~/.claude/retro/LESSONS.md"
fi

case "$REPO" in
  "$HOME"/*) IMPORT="@~/${REPO#"$HOME"/}/CLAUDE.md" ;;
  *)         IMPORT="@$REPO/CLAUDE.md" ;;
esac
touch "$CLAUDE_DIR/CLAUDE.md"
if [ "$IMPORT" != "@$REPO/CLAUDE.md" ] && grep -qxF "@$REPO/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"; then
  grep -vxF "@$REPO/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md" > "$CLAUDE_DIR/CLAUDE.md.tmp" || true
  mv "$CLAUDE_DIR/CLAUDE.md.tmp" "$CLAUDE_DIR/CLAUDE.md"
  echo "replaced the absolute import with $IMPORT"
fi
if ! grep -qxF "$IMPORT" "$CLAUDE_DIR/CLAUDE.md"; then
  tmp="$(mktemp)"
  { echo "$IMPORT"; echo; cat "$CLAUDE_DIR/CLAUDE.md"; } > "$tmp"
  mv "$tmp" "$CLAUDE_DIR/CLAUDE.md"
  echo "added   $IMPORT to $CLAUDE_DIR/CLAUDE.md"
fi

if ls -d "$CLAUDE_DIR"/plugins/cache/*/superpowers >/dev/null 2>&1; then
  echo "note: the superpowers plugin is no longer needed. Remove it with: claude plugin uninstall superpowers"
fi
if [ -e "$CLAUDE_DIR/skills/session-cost-review" ]; then
  echo "note: ~/.claude/skills/session-cost-review is now merged into ckore-retro; remove it so only one triggers."
fi
command -v node >/dev/null 2>&1 || echo "note: node isn't on PATH; ckore-design's visual companion needs it."
echo "done. Private profiles, skills and your lessons ledger belong in an overlay repo (--overlay), never in this one."
