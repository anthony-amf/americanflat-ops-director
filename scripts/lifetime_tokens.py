#!/usr/bin/env python3
"""Total up every token Claude Code has used on this machine.

Claude Code keeps a transcript of every session as a .jsonl file under
~/.claude/projects/<project>/<session-id>.jsonl. Each assistant reply in
there carries a "usage" block with its token counts. This script reads all
of them and adds everything up.

Read-only: it opens the transcripts and prints numbers. It never writes,
moves, or removes anything.

    python3 scripts/lifetime_tokens.py                 # everything, all time
    python3 scripts/lifetime_tokens.py --by-month      # add a month-by-month table
    python3 scripts/lifetime_tokens.py --by-project    # add a per-project table
    python3 scripts/lifetime_tokens.py --since 2026-01-01
    python3 scripts/lifetime_tokens.py --dir /some/other/.claude/projects

The four kinds of tokens:
  input        text sent to the model fresh (billed full price)
  cache write  text stored for reuse on later turns
  cache read   text reused from that store (much cheaper than input)
  output       text the model wrote back

Note on dollars: this prints tokens only. A Claude subscription isn't
billed per token, and API list prices change, so any dollar figure here
would be a guess. Use the usage page in your account for real spend.
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from glob import glob

FIELDS = (
    ("input_tokens", "input"),
    ("cache_creation_input_tokens", "cache write"),
    ("cache_read_input_tokens", "cache read"),
    ("output_tokens", "output"),
)


def new_bucket():
    return {label: 0 for _, label in FIELDS} | {"replies": 0}


def add(bucket, usage):
    for key, label in FIELDS:
        bucket[label] += usage.get(key) or 0
    bucket["replies"] += 1


def total(bucket):
    return sum(bucket[label] for _, label in FIELDS)


def scan(paths, since):
    """Walk the transcripts and return (overall, by_model, by_month, by_project, stats)."""
    overall = new_bucket()
    by_model = defaultdict(new_bucket)
    by_month = defaultdict(new_bucket)
    by_project = defaultdict(new_bucket)
    seen = set()          # request ids already counted, so retries/replays don't double-count
    sessions = set()
    skipped_dupes = 0
    bad_lines = 0

    for path in paths:
        project = os.path.basename(os.path.dirname(path))
        try:
            handle = open(path, encoding="utf-8", errors="replace")
        except OSError as err:
            print(f"  (couldn't read {path}: {err})", file=sys.stderr)
            continue
        with handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    bad_lines += 1
                    continue
                message = row.get("message") or {}
                usage = message.get("usage")
                if not isinstance(usage, dict):
                    continue
                if message.get("role") not in (None, "assistant"):
                    continue

                stamp = row.get("timestamp") or ""
                if since and stamp and stamp[:10] < since:
                    continue

                # One reply can appear more than once in a transcript (a resumed
                # session replays earlier turns). The request id is what makes it
                # the same model call, so count each id once.
                request_id = row.get("requestId")
                if request_id:
                    if request_id in seen:
                        skipped_dupes += 1
                        continue
                    seen.add(request_id)

                add(overall, usage)
                add(by_model[message.get("model") or "unknown"], usage)
                add(by_month[stamp[:7] or "undated"], usage)
                add(by_project[project], usage)
                if row.get("sessionId"):
                    sessions.add(row["sessionId"])

    stats = {
        "sessions": len(sessions),
        "files": len(paths),
        "skipped_dupes": skipped_dupes,
        "bad_lines": bad_lines,
    }
    return overall, by_model, by_month, by_project, stats


def commas(n):
    return f"{n:,}"


def millions(n):
    return f"{n / 1_000_000:,.1f}M" if n >= 1_000_000 else commas(n)


def print_table(title, buckets, name_header, by_name=False):
    if by_name:
        rows = sorted(buckets.items())
    else:
        rows = sorted(buckets.items(), key=lambda kv: -total(kv[1]))
    width = max([len(name_header)] + [len(name) for name, _ in rows])
    header = f"{name_header:<{width}}  {'total':>13}  " + "  ".join(
        f"{label:>13}" for _, label in FIELDS
    )
    print(f"\n{title}")
    print(header)
    print("-" * len(header))
    for name, bucket in rows:
        cells = "  ".join(f"{commas(bucket[label]):>13}" for _, label in FIELDS)
        print(f"{name:<{width}}  {commas(total(bucket)):>13}  {cells}")


def main():
    parser = argparse.ArgumentParser(
        description="Add up all the tokens Claude Code has used on this machine."
    )
    parser.add_argument(
        "--dir",
        action="append",
        default=None,
        help="Transcript folder to read (repeatable). Default: ~/.claude/projects",
    )
    parser.add_argument(
        "--since", metavar="YYYY-MM-DD", help="Only count activity on or after this date"
    )
    parser.add_argument("--by-month", action="store_true", help="Add a month-by-month table")
    parser.add_argument("--by-project", action="store_true", help="Add a per-project table")
    args = parser.parse_args()

    roots = args.dir or [os.path.expanduser("~/.claude/projects")]
    paths = []
    for root in roots:
        root = os.path.expanduser(root)
        if not os.path.isdir(root):
            print(f"No transcript folder at {root}", file=sys.stderr)
            continue
        paths.extend(sorted(glob(os.path.join(root, "**", "*.jsonl"), recursive=True)))

    if not paths:
        print("Found no transcripts to read. Nothing to count.")
        return 1

    overall, by_model, by_month, by_project, stats = scan(paths, args.since)

    span = f" since {args.since}" if args.since else " (all time)"
    print(f"Claude Code token usage{span}")
    print(f"Read {stats['files']} transcript file(s) covering {stats['sessions']} session(s).")
    if stats["skipped_dupes"]:
        print(f"Ignored {commas(stats['skipped_dupes'])} repeated reply(ies) so nothing is counted twice.")
    if stats["bad_lines"]:
        print(f"Skipped {commas(stats['bad_lines'])} unreadable line(s).")

    grand = total(overall)
    print(f"\nGrand total: {commas(grand)} tokens ({millions(grand)}) across {commas(overall['replies'])} model replies")
    for _, label in FIELDS:
        share = (overall[label] / grand * 100) if grand else 0
        print(f"  {label:<12} {commas(overall[label]):>15}  {share:5.1f}%")

    print_table("By model", by_model, "model")
    if args.by_month:
        print_table("By month", by_month, "month", by_name=True)
    if args.by_project:
        print_table("By project", by_project, "project")
    return 0


if __name__ == "__main__":
    sys.exit(main())
