#!/bin/sh
# Reruns the multitask checks into check/<name>/ (chart.mmd and report.md; tlc.out is not kept).
# Usage: sh run-checks.sh [name ...]   (no name: every family for each design, then each leave-one-out)
#   <family>-today     the code at 04f083a
#   <family>-decided   the boss's decided design (#2-#8)
#   <family>-proposed  the decided design plus P1-P8 (design.md)
#   without/P<n>       the proposed design without one change, in the family that change is for
set -eu
cd "$(dirname "$0")"
tool="${STATECHART:-$HOME/.agents/skills/statechart/scripts/statechart}"
all=""
for family in small cross notice ends; do
  for design in today decided proposed; do all="$all $family-$design"; done
done
for p in P1 P2 P3 P4 P5 P6 P7 P8; do all="$all without/$p"; done
all="$all causes/owed-1 causes/owed-2 causes/owed-3 causes/spam-1 causes/back-1"
for name in ${*:-$all}; do
  case "$name" in
    without/P1 | without/P3 | without/P4) family=cross ;;
    without/P2) family=small ;;
    causes/back-*) family=cross ;;
    without/P5 | without/P6 | causes/*) family=notice ;;
    without/P7 | without/P8) family=ends ;;
    *) family="${name%%-*}" ;;
  esac
  case "$name" in
    without/*) design="proposed without ${name#without/}" ;;
    causes/*) design="cause ${name#causes/}" ;;
    *) design="${name#*-}" ;;
  esac
  view=view.mjs
  [ "$family" = small ] && view=view-small.mjs
  reviews=0; { [ "$family" = cross ] || [ "$family" = notice ]; } && reviews=1
  lands=0; [ "$family" = ends ] && lands=1
  out="check/$name"
  rm -rf "$out"
  # The command exits 1 when a rule breaks; the report says which.
  MULTITASK_DESIGN="$design" MULTITASK_REVIEWS=$reviews MULTITASK_LANDS=$lands \
    "$tool" MultiTask.tla --config "$name.cfg" --view "$view" --out "$out" >/dev/null || [ -f "$out/report.md" ]
  rm -f "$out"/tlc*.out
  echo "$name: breaks [$(sed -n 's/^## \(.*\) breaks$/\1/p' "$out/report.md" | tr '\n' ' ')] $(grep -A1 '^## Rules not checked' "$out/report.md" | tr '\n' ' ')"
done
