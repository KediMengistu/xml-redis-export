"""Command-line entry point: python -m app.main [-v] /path/to/xml"""

import argparse
import os
import sys

import redis

from app.exporter import build_keys, read_back, save
from app.xml_parser import ConfigError, parse_config


def connect_to_redis():
    return redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        decode_responses=True,
    )


def run(argv, make_client=connect_to_redis, out=None, err=None) -> int:
    """Run the export and return the process exit code (0 = success)."""
    out = out or sys.stdout
    err = err or sys.stderr

    parser = argparse.ArgumentParser(
        prog="export.sh", description="Export subdomains and cookies from an XML file to Redis."
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="print every key saved to Redis with its value"
    )
    parser.add_argument("xml_path", help="path to the XML file")
    args = parser.parse_args(argv)

    # Parse everything first, so a bad file never touches Redis.
    try:
        data = parse_config(args.xml_path)
    except ConfigError as e:
        print(f"Error: {e}", file=err)
        return 1
    for warning in data.warnings:
        print(f"Warning: {warning}", file=err)

    keys = build_keys(data)
    client = make_client()
    try:
        save(client, keys)
        # Read the values back from Redis so -v shows what was actually stored.
        saved = read_back(client, sorted(keys)) if args.verbose else {}
    except redis.RedisError as e:
        print(f"Error: could not write to Redis: {e}", file=err)
        return 1

    print(
        f"Saved {len(keys)} keys to Redis: 'subdomains' ({len(data.subdomains)} URLs) "
        f"and {len(data.cookies)} cookie keys.",
        file=out,
    )
    for key, value in saved.items():
        print(f"{key} = {value}", file=out)
    return 0


def main():
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
