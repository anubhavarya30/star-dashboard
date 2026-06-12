#!/usr/bin/env bash
# STAR auto-save: commit AND push any work when a Claude turn ends.
# Wired as a Stop hook in .claude/settings.local.json so the user never has to
# ask to "save" again. Commits locally, then pushes to origin.
set -euo pipefail
cd "$(dirname "$0")/.." || exit 0

# 1) commit any uncommitted work (skip if the tree is clean)
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  git commit -q -m "autosave: ${ts}

Auto-committed by Stop hook (scripts/autosave.sh).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" || true
fi

# 2) push if the local branch is ahead of its upstream (quietly; never fail the
#    turn if offline / no upstream / auth prompt — autosave must stay non-blocking)
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
if [ -n "$(git log "@{u}.." 2>/dev/null)" ] || ! git rev-parse "@{u}" >/dev/null 2>&1; then
  # GIT_TERMINAL_PROMPT=0 → never block on a credential prompt; fail fast instead.
  GIT_TERMINAL_PROMPT=0 git push -q origin "$branch" >/dev/null 2>&1 || true
fi
