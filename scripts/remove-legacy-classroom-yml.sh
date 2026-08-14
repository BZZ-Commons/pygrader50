#!/usr/bin/env bash
#
# Removes the legacy GitHub Classroom grading workflow (.github/workflows/
# classroom.yml) from the templates a migrated classroom uses, and from the
# student repos that already accepted an assignment.
#
#   scripts/remove-legacy-classroom-yml.sh <org> <classroom>            # dry run
#   scripts/remove-legacy-classroom-yml.sh <org> <classroom> --apply    # delete
#
# The target list comes from the `template` block of the classroom's
# assignments.json, NOT from listing the template organisation: that org also
# holds templates for modules still running on the old pygrader path, and
# deleting their workflow would silently stop grading there.
#
# Template edits never reach repos that already exist — a student repo carries
# its own copy from creation time, which is why the student repos are handled
# separately here.
#
# Safe to re-run: a repo without the file is reported as "absent" and skipped.
# Written for bash 3.2 (macOS default): no mapfile, no arrays of targets.
set -uo pipefail

ORG=${1:-}
CLASSROOM=${2:-}
APPLY=0
[ "${3:-}" = "--apply" ] && APPLY=1

if [ -z "$ORG" ] || [ -z "$CLASSROOM" ]; then
  echo "usage: $0 <org> <classroom> [--apply]" >&2
  echo "example: $0 m320-ix25 m320-ix25 --apply" >&2
  exit 2
fi

CONFIG_REPO="$ORG/classroom50"
FILE=.github/workflows/classroom.yml
TARGETS=$(mktemp)
trap 'rm -f "$TARGETS"' EXIT

MSG='chore: remove GitHub Classroom autograding workflow

Grading moved to Classroom 50, which runs the classroom default autograder
from the config repo. The classroom.yml grading job called the retired
pygrader workflow and passed the Moodle token into every student run via
secrets: inherit.'

echo "== collecting targets from $CONFIG_REPO =="

gh api "repos/$CONFIG_REPO/contents/$CLASSROOM/assignments.json" \
   -H 'Accept: application/vnd.github.raw' \
  | jq -r '.assignments[] | "\(.template.owner)/\(.template.repo)"' \
  | sort -u >> "$TARGETS" \
  || { echo "could not read $CLASSROOM/assignments.json from $CONFIG_REPO" >&2; exit 1; }
echo "templates: $(wc -l < "$TARGETS" | tr -d ' ')"

# Student repos that actually exist. The config repo lives in the same org and
# is not a student repo.
gh repo list "$ORG" --limit 1000 --json name --jq '.[].name' \
  | grep -v '^classroom50$' \
  | sed "s|^|$ORG/|" >> "$TARGETS"

echo "total targets: $(wc -l < "$TARGETS" | tr -d ' ')"
[ "$APPLY" -eq 1 ] || echo '(dry run — pass --apply to delete)'

deleted=0; absent=0; failed=0
while read -r repo; do
  [ -n "$repo" ] || continue
  # Probe by exit code, not by output: on 404 `gh api --jq` prints the error
  # body to stdout, so capturing it would make every missing file look present.
  if ! gh api "repos/$repo/contents/$FILE" >/dev/null 2>&1; then
    echo "absent   $repo"
    absent=$((absent + 1))
    continue
  fi
  if [ "$APPLY" -eq 0 ]; then
    echo "would rm $repo"
    deleted=$((deleted + 1))
    continue
  fi
  sha=$(gh api "repos/$repo/contents/$FILE" --jq '.sha' 2>/dev/null)
  if gh api -X DELETE "repos/$repo/contents/$FILE" \
       -f message="$MSG" -f sha="$sha" --jq '.commit.sha' >/dev/null 2>&1; then
    echo "deleted  $repo"
    deleted=$((deleted + 1))
  else
    echo "FAILED   $repo"
    failed=$((failed + 1))
  fi
done < "$TARGETS"

echo "== deleted/would-delete: $deleted  absent: $absent  failed: $failed =="
[ "$failed" -eq 0 ]
