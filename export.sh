#!/usr/bin/env bash
# Export subdomains and cookies from an XML file to Redis.
# Usage: ./export.sh [-v] /path/to/xml
set -euo pipefail

usage() {
  echo "Usage: $0 [-v] /path/to/xml" >&2
  exit 1
}

app_args=()
while getopts ":v" opt; do
  case "$opt" in
    v) app_args+=(-v) ;;
    *) usage ;;
  esac
done
shift $((OPTIND - 1))
[ $# -eq 1 ] || usage

xml="$1"
if [ ! -f "$xml" ]; then
  echo "Error: file not found: $xml" >&2
  exit 1
fi

# Absolute path of the file for the Docker mount. On Windows (Git Bash),
# "pwd -W" gives a C:/... path that Docker Desktop understands.
xml_dir="$(cd "$(dirname "$xml")" && { pwd -W 2>/dev/null || pwd; })"
xml_path="$xml_dir/$(basename "$xml")"

# Stop Git Bash rewriting container paths like /data/input.xml into Windows paths.
export MSYS_NO_PATHCONV=1

cd "$(dirname "${BASH_SOURCE[0]}")"
docker compose build --quiet app
# The file is mounted read-only; the app never sees anything else on this machine.
docker compose run --rm --quiet-pull \
  --volume "$xml_path:/data/input.xml:ro" \
  app ${app_args[@]+"${app_args[@]}"} /data/input.xml
