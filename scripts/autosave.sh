#!/usr/bin/env bash
# STAR auto-save: commit any uncommitted work when a Claude turn ends.
# Wired as a Stop hook in .claude/settings.local.json so the user never has to
# ask to "save" again. Local commit only — pushing stays manual/explicit.
set -euo pipefail
cd "$(dirname "$0")/.." || exit 0
# nothing staged/unstaged/untracked? exit quietly.
if [ -z "$(git status --porcelain)" ]; then exit 0; fi
git add -A
ts="$(date '+%Y-%m-%d %H:%M:%S')"
git commit -q -m "autosave: ${ts}

Auto-committed by Stop hook (scripts/autosave.sh).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" || true
