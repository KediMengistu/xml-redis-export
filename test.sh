#!/usr/bin/env bash
# Run the unit tests inside Docker. Extra arguments go to pytest, e.g. ./test.sh -v
set -euo pipefail

export MSYS_NO_PATHCONV=1
cd "$(dirname "${BASH_SOURCE[0]}")"
docker compose build --quiet tests
docker compose run --rm tests "$@"
