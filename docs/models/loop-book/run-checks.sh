#!/bin/sh
# Reruns every check of the model into check/<name>/ (chart.mmd and report.md; tlc.out is not kept).
# Usage: sh run-checks.sh [name ...]   (no name: all)
set -eu
cd "$(dirname "$0")"
tool="${STATECHART:-$HOME/.agents/skills/statechart/scripts/statechart}"
all="small full held units subsession inline causes/kept-1 causes/kept-2 causes/kept-3 causes/reported-1 causes/finish-1 causes/quiet-1 causes/quiet-2 causes/stale-1 causes/read-1"
for name in ${*:-$all}; do
  view=view.mjs
  [ "$name" = small ] && view=view-small.mjs
  kind=reviewed
  [ "$name" = inline ] && kind=inline
  out="check/$name"
  rm -rf "$out"
  # The command exits 1 when a rule breaks; the report says which.
  LOOPBOOK_KIND=$kind "$tool" LoopBook.tla --config "$name.cfg" --view "$view" --out "$out" >/dev/null || [ -f "$out/report.md" ]
  rm -f "$out"/tlc*.out
  echo "$name: breaks [$(sed -n 's/^## \(.*\) breaks$/\1/p' "$out/report.md" | tr '\n' ' ')] $(grep -A1 '^## Rules not checked' "$out/report.md" | tr '\n' ' ')"
done
