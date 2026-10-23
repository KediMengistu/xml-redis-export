# XML → Redis export

A small command-line app that reads `config.xml` and saves its data to Redis:

| Redis key | Value |
|---|---|
| `subdomains` | JSON array of every `<subdomain>`, in file order, e.g. `["http://secureline.tools.avast.com", "http://gf.tools.avast.com", ...]` |
| `cookie:%NAME%:%HOST%` | Text of each `<cookie>`, e.g. `cookie:dlp-avast:amazon` → `mmm_amz_dlp_777_ppc_m` |

Python 3.13 app container + Redis 7.4 container, wired together with Docker Compose.

## Quick start

Requirements: Docker with Compose v2, and a bash shell (Linux/macOS terminal, or Git Bash on Windows).

```bash
./export.sh -v ./config.xml     # export and print every saved key with its value
./export.sh ./config.xml        # export and print a one-line summary
./test.sh                       # run the unit tests (inside Docker)
```

Example output:

```
$ ./export.sh -v config.xml
Saved 47 keys to Redis: 'subdomains' (38 URLs) and 46 cookie keys.
cookie:dlp-avast:01net = mmm_net_dlp_777_ppc_m
cookie:dlp-avast:amazon = mmm_amz_dlp_777_ppc_m
...
cookie:dlp-avg:vector = mmm_vct_dlp_779_ppc_m
subdomains = ["http://secureline.tools.avast.com", "http://gf.tools.avast.com", ...]
```

Redis keeps running after the export so the data can be inspected:

```bash
docker compose exec redis redis-cli get cookie:dlp-avast:amazon
docker compose down             # stop and remove the containers
```

Exit code is `0` on success and `1` on any error (bad arguments, missing or invalid file, Redis unavailable).

## How it works

```
export.sh ──► docker compose run app ──► app/main.py
                 (file mounted                │
                  read-only)                  ├─► xml_parser.parse_config()  XML → ExportData
                                              ├─► exporter.build_keys()      ExportData → {key: value}
                                              └─► exporter.save(client, …)   one MULTI/EXEC transaction
```

| File | Responsibility |
|---|---|
| [`app/xml_parser.py`](app/xml_parser.py) | Safely parses and validates the XML into plain data. No Redis code. |
| [`app/exporter.py`](app/exporter.py) | Builds key names/values and writes them through a Redis client it is given. |
| [`app/main.py`](app/main.py) | CLI: arguments, wiring, messages and exit codes. |
| [`export.sh`](export.sh) | Validates arguments, mounts the XML file into the container, runs the app. |
| [`docker-compose.yml`](docker-compose.yml) | `redis`, `app`, and a `tests` service (behind a profile). |
| [`Dockerfile`](Dockerfile) | Multi-stage: `app` (runtime only) and `test` (adds pytest + fakeredis). |

## Design decisions

- **Parsing is separate from writing.** The parser returns a dataclass and knows nothing about Redis, so it is tested with plain files. The exporter takes the Redis client as an argument (dependency injection), and `main.run()` takes a client factory and output streams, so every layer is unit-tested with [fakeredis](https://github.com/cunla/fakeredis-py) and no running database.
- **Validate everything before writing anything.** The whole file is parsed first; if anything is wrong the app exits with a clear message and Redis is not touched.
- **Idempotent, clean replace.** Each run deletes the previous `subdomains` and `cookie:*` keys and writes the new set inside a single `MULTI/EXEC` transaction. Running twice gives the same result, a cookie removed from the XML also disappears from Redis, and readers never see a half-written export. Keys outside these names are left alone.
- **`-v` reads back from Redis** rather than echoing the parsed data, so it shows what was actually stored. Output is sorted for stable, diff-able results.
- **Python** was chosen (the task allows "or other language") because it keeps the solution short and readable, has a well-known XXE-safe parser, and needs no build step.

## Assumptions about the data

- Values are kept **exactly as in the file**, apart from trimming surrounding whitespace (the file mixes tabs and spaces). Apparent typos (`donwloaden`, `homepate`) and the capitalised `Mmm_fhp_dlp_779_ppc_m` are treated as data, not corrected.
- Subdomains are stored in file order. Duplicates would be kept, since the task asks for "all subdomains".
- If the same cookie name + host appears twice, the last value wins and a warning is printed.
- XML comments are ignored. Both `<subdomains>` and `<cookies>` must exist but may be empty. A cookie without `name`, `host` or a value, or an empty `<subdomain>`, is an error.

## Security

- XML is parsed with [`defusedxml`](https://pypi.org/project/defusedxml/), which rejects entity declarations and external references (XXE, "billion laughs"). Tests cover both.
- The Redis port is **not published**: Redis is reachable only from the app over the private Compose network.
- The XML file is mounted **read-only**, and only that one file is mounted.
- The app container runs as a non-root user, and the runtime image contains no test tooling.
- The URLs are stored as text only. The app makes no network calls other than to Redis.
- Dependencies are pinned to exact versions.

## Tests

```bash
./test.sh        # all tests
./test.sh -v     # with test names
```

30 tests across [`tests/`](tests/): parsing of the real `config.xml` (counts, quirks), whitespace and comments, every error case, XXE rejection, key format and JSON, clean replace and idempotency, unrelated keys untouched, `-v` output, and Redis-unavailable handling.

To run them without Docker: `pip install -r requirements-dev.txt && python -m pytest`.

## What I would improve with more time

- **Show the original file name in errors.** The app only sees the container path, so errors mention `/data/input.xml`. `export.sh` could pass the original name in an environment variable.
- **Fully atomic replace under concurrent writers.** The `SCAN` for old keys runs just before the transaction. That is fine for a single batch job, but with concurrent exports I would use `WATCH`, or write to a versioned key prefix and switch a pointer key.
- **Integration test against real Redis** in Compose, in addition to the fakeredis unit tests.
- **CI** (GitHub Actions) running the tests, plus `ruff` and `mypy`.
- **Stricter input validation:** an XSD schema, URL format checks, and rejecting `:` inside cookie names/hosts (it would make keys ambiguous).
- **Redis authentication (ACL/password) via secrets** if Redis were ever shared or not local-only.
