#!/usr/bin/env bash
# Install pieces of this repository by hand, for people who do not use the
# Claude Code plugin system (Codex users, or a plain shell setup).
#
#   ./install.sh                 interactive menu
#   ./install.sh --list          what is available
#   ./install.sh cli skill       install those, no questions
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_SKILLS="${HOME}/.claude/skills"
CODEX_PROMPTS="${HOME}/.codex/prompts"
BIN_DIR="${DOCSHOT_BIN_DIR:-${HOME}/.local/bin}"

say() { printf '%s\n' "$*"; }

list() {
  cat <<'ITEMS'
  cli      docshot on your PATH (symlink into ~/.local/bin)
  skill    the write-manual skill for Claude Code (~/.claude/skills)
  codex    the write-manual prompt for Codex (~/.codex/prompts)
ITEMS
}

install_cli() {
  mkdir -p "$BIN_DIR"
  ln -sfn "$ROOT/plugins/docshot/bin/docshot" "$BIN_DIR/docshot"
  say "✓ docshot -> $BIN_DIR/docshot"
  case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) say "  ! $BIN_DIR is not on your PATH — add it to your shell profile" ;;
  esac
  command -v python3 >/dev/null || say "  ! python3 not found — 'docshot build' needs it"
  command -v node >/dev/null || say "  ! node not found — 'docshot capture' needs it"
}

install_skill() {
  mkdir -p "$CLAUDE_SKILLS"
  rm -rf "$CLAUDE_SKILLS/write-manual"
  cp -R "$ROOT/plugins/docshot/skills/write-manual" "$CLAUDE_SKILLS/write-manual"
  say "✓ write-manual skill -> $CLAUDE_SKILLS/write-manual"
}

install_codex() {
  mkdir -p "$CODEX_PROMPTS"
  cp "$ROOT/codex/prompts/write-manual.md" "$CODEX_PROMPTS/write-manual.md"
  say "✓ write-manual prompt -> $CODEX_PROMPTS/write-manual.md (use it as /write-manual)"
}

install_one() {
  case "$1" in
    cli) install_cli ;;
    skill) install_skill ;;
    codex) install_codex ;;
    *) say "unknown item: $1"; say "available:"; list; exit 1 ;;
  esac
}

if [ "${1:-}" = "--list" ]; then
  list
  exit 0
fi

if [ "$#" -gt 0 ]; then
  for item in "$@"; do install_one "$item"; done
  exit 0
fi

say "What do you want to install?"
list
say ""
printf 'items (space separated, or "all"): '
read -r answer
[ "$answer" = "all" ] && answer="cli skill codex"
[ -z "$answer" ] && { say "nothing to do"; exit 0; }
for item in $answer; do install_one "$item"; done
