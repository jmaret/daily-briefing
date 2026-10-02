#!/bin/bash
# Run the test suite when an agent turn ends. On failure, ask the agent to fix it.
cat >/dev/null

root="$(cd "$(dirname "$0")/../.." && pwd)"
python="$root/.venv/bin/python"

if [[ ! -x "$python" ]]; then
  printf '%s\n' '{"followup_message":"Tests were not run because .venv/bin/python is missing. Install the requirements into .venv, then run pytest."}'
  exit 0
fi

output="$("$python" -m pytest -q 2>&1)"
status=$?

if [[ $status -ne 0 ]]; then
  printf '%s' "$output" | "$python" -c 'import json,sys; print(json.dumps({"followup_message": "pytest failed. Fix the code or tests.\n\n" + sys.stdin.read()}))'
  exit 0
fi

printf '%s\n' '{}'
exit 0
