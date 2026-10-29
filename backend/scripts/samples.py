# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "boto3[crt]>=1.43.120",
#     "httpx>=0.28.1",
#     "numpy>=2.5.4",
#     "opencv-python-headless>=4.14.0.94,<5",
# ]
# ///
"""Seed, remove and check the samples (C512, MS4-Q8, MS4-Q14; MS4 spec §4.5; Task 8).

- `seed --ids <id>...`: each id is an open-licensed manifest id or a consented
  item_id, checked against the one allow-list (guards.py); any other is refused, and
  so is a source without a capture date (no_date). Each candidate runs once in the
  cloud as an eval seed (`eval_runs.eval_item(..., seed=True)`), its photo sent as the
  app sends it. It qualifies only if its seed gave a level or a clear no flood seen
  (final status done) with a stored, blurred copy: that copy, never the original, is
  copied untagged to samples/{sampleId}.jpg, since the API role has no tagging grant,
  and entered in samples/manifest.json with its seed's saved result (MS4-Q8 (b)). A
  refused seed is skipped under refused, a failed one under failed, and one without a
  copy under no_copy. Its last line gives how many candidates it was given and how
  many qualified. Set A photos never become samples.
- `remove [sampleId]`: one sample's manifest entry, photo and source note, as when a
  donor withdraws (MS10's P6), or with no id every samples/ object, the manifest
  included, and every source note.
- `check [--run]`: counts the listed samples whose photoUrl answers 200. With --run it
  runs the first through POST /samples/{id}, with a fresh uuid4 in X-Lusot-Device so
  it never uses the shared none bucket, and prints its mode, its outcome and whether
  it is on the map (S5).

Each sample's source note goes to LUSOT_DATA_DIR\\samples\\sample_sources.csv only,
never to S3 or the repo. Each seed's Meta calls run on the credits, about $0.03 a
photo. Output: counts, outcomes and ids, through guards.say.

Usage: uv run backend/scripts/samples.py seed --ids OL022 S001
       uv run backend/scripts/samples.py remove [sampleId]
       uv run backend/scripts/samples.py check [--run]
Exit codes: 0 done (seed: at least one qualified); 1 a check failed, none qualified,
or not found; 2 refused by a guard.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
import uuid
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

import httpx
from botocore.exceptions import BotoCoreError, ClientError
from eval_runs import api_client, eval_item, item_outcome, new_report_id, wait_item
from guards import (
    Source,
    allowed_sources,
    approved_m9_versions,
    data_dir,
    refuse_sealed,
    say,
)
from ops_common import PHT, WAIT_S, counts, guarded, lusot_session, yes
from smoke_upload import (
    CheckFailed,
    as_app_jpeg,
    load_stack,
    outcome_of,
    wait_final,
)

MANIFEST_KEY = "samples/manifest.json"
SOURCES_CSV = ("samples", "sample_sources.csv")
NOTE_COLUMNS = ["sampleId", "source_id", "note"]
SAMPLE_ID = re.compile(r"s[0-9a-f]{10}")
LEVEL_FIELDS = {
    "level": "S",
    "landmark": "S",
    "passability": "S",
    "levelIsFloor": "BOOL",
}


def sample_id(source_id: str) -> str:
    """A sample's id, fixed by its source so a re-seed replaces it."""
    return "s" + hashlib.sha256(("sample:" + source_id).encode()).hexdigest()[:10]


def main(
    argv: Sequence[str] | None = None,
    *,
    session=None,
    http: httpx.Client | None = None,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    seed = commands.add_parser(
        "seed", help="seed candidates, keeping those that qualify"
    )
    seed.add_argument("--ids", nargs="+", required=True, help="source ids")
    remove = commands.add_parser("remove", help="remove one sample, or every sample")
    remove.add_argument("sample_id", nargs="?")
    check = commands.add_parser("check", help="check the samples as the app sees them")
    check.add_argument("--run", action="store_true", help="run the first sample")

    def command() -> int:
        args = parser.parse_args(argv)
        if args.command == "seed":
            return seed_samples(args, session, clock, sleep)
        if args.command == "remove":
            return remove_samples(args, session)
        return check_samples(args, session, http, clock, sleep)

    return guarded(
        command,
        shown=(CheckFailed,),
        errors=(BotoCoreError, ClientError, httpx.HTTPError),
    )


def seed_samples(args, session, clock, sleep) -> int:
    refuse_sealed(data_dir())
    session = session or lusot_session()
    stack = load_stack(session)
    sources, refused = allowed_sources(args.ids, approved_m9_versions())
    ddb, s3 = session.client("dynamodb"), session.client("s3")
    table, bucket = stack.output("TableName"), stack.bucket
    saved_at = datetime.fromtimestamp(clock(), PHT).strftime("%Y-%m-%d")
    seed_refused: Counter = Counter()
    seed_failed: Counter = Counter()
    no_copy = qualified = 0
    for source in sources.values():
        if not source.date:
            refused["no_date"] += 1
            continue
        try:
            jpeg = as_app_jpeg(source.photo)  # before any write
        except (CheckFailed, OSError):
            refused["unreadable"] += 1
            continue
        report_id = new_report_id()
        item = eval_item(report_id, int(clock()), seed=True)
        # The item first, so the photo's event finds it.
        ddb.put_item(TableName=table, Item=item)
        s3.put_object(
            Bucket=bucket,
            Key=f"raw/{report_id}.jpg",
            Body=jpeg,
            ContentType="image/jpeg",
        )
        key = {"pk": item["pk"], "sk": item["sk"]}
        final = wait_item(ddb, table, key, bound_s=WAIT_S, clock=clock, sleep=sleep)
        outcome = item_outcome(final)
        status = final.get("status", {}).get("S")
        if status != "done":
            reason = final.get("refusalReason", {}).get("S") or outcome
            (seed_refused if status == "refused" else seed_failed)[reason] += 1
            say(f"{report_id}: skipped, {outcome}")
            continue
        # Only the seed's own stored copy, which the pipeline blurred.
        photo_key = final.get("photoKey", {}).get("S")
        if photo_key != f"blurred/{report_id}.jpg":
            no_copy += 1
            say(f"{report_id}: skipped, {outcome} with no stored copy")
            continue
        sid = sample_id(source.source_id)
        # REPLACE with no Tagging leaves the copy untagged (Context7, S3's CopyObject):
        # the API role, which copies it to raw/ for each run, has no tagging grant.
        s3.copy_object(
            Bucket=bucket,
            CopySource=f"{bucket}/{photo_key}",
            Key=f"samples/{sid}.jpg",
            TaggingDirective="REPLACE",
        )
        write_note(sid, source)
        manifest = read_manifest(s3, bucket)
        entries = [e for e in manifest["samples"] if e.get("sampleId") != sid]
        entries.append(manifest_entry(sid, source, final, saved_at))
        write_manifest(s3, bucket, {"version": 1, "samples": entries})
        qualified += 1
        say(f"{sid}: qualified, {outcome} (seed {report_id})")
    if refused:
        say(f"refused before any run: {counts(refused)}")
    say(
        f"skipped: {skipped('refused', seed_refused)}, {skipped('failed', seed_failed)},"
        f" no_copy {no_copy}"
    )
    say(f"seed: {len(args.ids)} candidates given, {qualified} qualified")
    return 0 if qualified else 1


def skipped(name: str, reasons: Counter) -> str:
    total = sum(reasons.values())
    return f"{name} {total} ({counts(reasons)})" if total else f"{name} 0"


def manifest_entry(sid: str, source: Source, final: dict, saved_at: str) -> dict:
    """The sample's manifest entry: its six public fields, then its seed's saved
    result, under GET /reports' names and on its rule (Task 6's SampleEntry)."""
    entry = {"sampleId": sid, "credit": source.credit, "license": source.license}
    if source.place:
        entry["place"] = source.place
    entry["date"] = source.date
    if source.event:
        entry["event"] = source.event
    no_flood = "level" not in final
    entry |= {"savedAt": saved_at, "status": "done", "noFloodSeen": no_flood}
    if not no_flood:
        for name, kind in LEVEL_FIELDS.items():
            entry[name] = final[name][kind]
    return entry


def read_manifest(s3, bucket: str) -> dict:
    """samples/manifest.json, or an empty one when it doesn't exist yet."""
    try:
        body = s3.get_object(Bucket=bucket, Key=MANIFEST_KEY)["Body"].read()
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "NoSuchKey":
            raise
        return {"version": 1, "samples": []}
    manifest = json.loads(body)
    if manifest.get("version") != 1:
        raise CheckFailed("samples/manifest.json isn't version 1")
    return manifest


def write_manifest(s3, bucket: str, manifest: dict) -> None:
    # No Tagging: the API role has no tagging grant (C512).
    s3.put_object(
        Bucket=bucket,
        Key=MANIFEST_KEY,
        Body=json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


def notes_path() -> Path:
    """lusot-data's sample_sources.csv, refused if sealed."""
    path = data_dir().joinpath(*SOURCES_CSV)
    refuse_sealed(path)
    return path


def read_notes(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as file:
        return {row["sampleId"]: row for row in csv.DictReader(file)}


def write_notes(path: Path, rows: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, NOTE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows.values())


def write_note(sid: str, source: Source) -> None:
    """The sample's private source note, in lusot-data only, one row per sample."""
    path = notes_path()
    rows = read_notes(path)
    rows[sid] = {"sampleId": sid, "source_id": source.source_id, "note": source.note}
    write_notes(path, rows)


def drop_notes(sid: str | None) -> None:
    """Drop one sample's source note or, with None, every one: a donor's withdrawal
    takes the note with the photo (MS10's P6), since it can name the donor."""
    path = notes_path()
    if not path.is_file():
        return
    kept = {} if sid is None else read_notes(path)
    kept.pop(sid, None)
    write_notes(path, kept)


def remove_samples(args, session) -> int:
    sid = args.sample_id
    if sid is not None and SAMPLE_ID.fullmatch(sid) is None:
        say("refused: that isn't a sample id")
        return 2
    refuse_sealed(data_dir())  # its source notes are in lusot-data
    session = session or lusot_session()
    stack = load_stack(session)
    s3 = session.client("s3")
    if sid is not None:
        # The entry first, so the list never points at a photo that is gone.
        manifest = read_manifest(s3, stack.bucket)
        kept = [e for e in manifest["samples"] if e.get("sampleId") != sid]
        listed = len(kept) < len(manifest["samples"])
        if listed:
            write_manifest(s3, stack.bucket, {"version": 1, "samples": kept})
        s3.delete_object(Bucket=stack.bucket, Key=f"samples/{sid}.jpg")
        drop_notes(sid)
        if listed:
            say(f"removed {sid}: its photo and its manifest entry")
            return 0
        say(f"{sid}: not in the manifest; its photo is deleted if it was there")
        return 1
    pages = s3.get_paginator("list_objects_v2").paginate(
        Bucket=stack.bucket, Prefix="samples/"
    )
    keys = [entry["Key"] for page in pages for entry in page.get("Contents", [])]
    for key in keys:
        s3.delete_object(Bucket=stack.bucket, Key=key)
    drop_notes(None)
    among = ", the manifest among them" if MANIFEST_KEY in keys else ""
    say(f"removed {len(keys)} samples/ objects{among}")
    return 0


def check_samples(args, session, http, clock, sleep) -> int:
    session = session or lusot_session()
    stack = load_stack(session)
    api = stack.api_url
    with api_client(http) as client:
        listed = client.get(f"{api}/samples")
        if listed.status_code != 200:
            say(f"check: GET /samples answered HTTP {listed.status_code}")
            return 1
        entries = listed.json().get("samples", [])
        working = sum(
            "photoUrl" in entry and client.get(entry["photoUrl"]).status_code == 200
            for entry in entries
        )
        say(f"check: {len(entries)} samples listed, {working} photos answer 200")
        passed = bool(entries) and working == len(entries)
        if args.run and entries:
            ran = run_one(client, api, entries[0]["sampleId"], clock, sleep)
            passed = passed and ran
    return 0 if passed else 1


def run_one(client: httpx.Client, api: str, sid: str, clock, sleep) -> bool:
    """POST /samples/{id} once, and whether its report is a sample's, off the map."""
    started = clock()
    device = {"X-Lusot-Device": str(uuid.uuid4())}  # never the shared none bucket
    response = client.post(f"{api}/samples/{sid}", headers=device)
    if response.status_code == 200 and response.json().get("saved") is True:
        saved_at = response.json().get("savedAt")
        say(
            f"run: model calls are paused, so the API served the result saved {saved_at}"
        )
        return True
    if response.status_code != 201:
        say(f"run: POST /samples/{{id}} answered HTTP {response.status_code}")
        return False
    report_id = response.json()["reportId"]
    body = wait_final(
        client, api, report_id, since=started, bound_s=WAIT_S, clock=clock, sleep=sleep
    )
    pins = client.get(f"{api}/map/pins")
    on_map = pins.status_code == 200 and any(
        pin.get("id") == report_id for pin in pins.json().get("pins", [])
    )
    say(
        f"{report_id}: mode {body.get('mode')}, {outcome_of(body)}, on the map:"
        f" {yes(on_map)}"
    )
    return body.get("mode") == "sample" and not on_map


if __name__ == "__main__":
    raise SystemExit(main())
