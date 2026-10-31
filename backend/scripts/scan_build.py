# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "boto3[crt]>=1.43.120",
#     "httpx>=0.28.1",
#     "numpy>=2.5.4",
#     "opencv-python-headless>=4.14.0.94,<5",
# ]
# ///
"""The build scan: the APK and the deployed web bundle (MS7 plan Task 6, C813).

It reads every member of an APK or zip (with no extraction) or every file of a folder,
and fails on:
- the Meta key's or the account ID's exact bytes, or their UTF-16LE form, in any member,
  binary ones such as classes.dex and resources.arsc included (Review Focus 5)
- a marker that only a wrong build carries: api.meta.ai, MODEL_API_KEY, or the mock
  API's LUSOT_MOCK_API
- a 12-digit run in a member that decodes as UTF-8, once hex runs of 32 or more are
  removed, as scripts/check_account_ids.mjs reads it
- gitleaks' own findings, over the APK unpacked into a fresh folder outside the repo
- for an APK, through aapt2: allowBackup true, a permission outside ALLOWED_PERMISSIONS,
  or a loggingBehavior other than none in assets/capacitor.config.json

--site URL first fetches the deployed index.html and the same-origin assets it and its
scripts and stylesheets name into a fresh folder under LUSOT_DATA_DIR\\ms7\\, and scans
that, so the scan reads what judges download, not a rebuild.

The key comes from MODEL_API_KEY and the account ID from sts, inside the run; neither is
ever printed. Findings name the secret and the member, with each secret's text and any
12-digit run masked in the member's name.

Usage: uv run backend/scripts/scan_build.py <apk or folder> [--aapt2 PATH]
       uv run backend/scripts/scan_build.py --site URL
Exit codes: 0 nothing found; 1 a finding; 2 refused (a sealed or in-repo folder, a
missing secret, or bad usage).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import zipfile
from collections.abc import Iterable, Iterator, Mapping, Sequence
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin, urlparse

import guards
import httpx
from harden import data_dir, ipv4_client, say, scrub
from ops_common import PHT, guarded, lusot_session
from smoke_upload import CheckFailed

REPO = Path(__file__).resolve().parents[2]
APP_ID = "io.github.rvbcosme.lusot"
ALLOWED_PERMISSIONS = frozenset(
    {
        "android.permission.INTERNET",
        "android.permission.ACCESS_NETWORK_STATE",
        "android.permission.ACCESS_COARSE_LOCATION",
        "android.permission.ACCESS_FINE_LOCATION",
        "android.permission.CAMERA",
        # AndroidX core adds this one to every app, for its own non-exported receivers.
        f"{APP_ID}.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION",
        # RECORD_AUDIO joins only once Ask Lusot's voice runs in the APK (Task 6's names).
    }
)
MARKERS = (b"api.meta.ai", b"MODEL_API_KEY", b"LUSOT_MOCK_API")
MAX_SITE_FILES = 500
_LONG_HEX = re.compile(r"(?<![0-9a-f])[0-9a-f]{32,}(?![0-9a-f])", re.IGNORECASE)
_TWELVE = re.compile(r"(?<![0-9])[0-9]{12}(?![0-9])")
# An attribute's link, a stylesheet's url(), or a quoted path a script imports or names
# (Vite's chunks are "./chunk-x.js" or "/assets/x.js").
_LINKS = re.compile(
    rb"""(?:src|href)\s*=\s*["']([^"']+)["']|url\(\s*["']?([^"')]+)["']?\s*\)"""
    rb"""|["'](\.{0,2}/[^"'\s]+\.(?:m?js|css|json|png|svg|webp|jpe?g|ico|woff2?|webmanifest))["']"""
)
_ANDROID = "http://schemas.android.com/apk/res/android:"


def _outside_the_repo(folder: Path) -> None:
    if guards.is_sealed(folder):
        raise CheckFailed("refused: a path inside a folder named sealed")
    resolved = folder.resolve()
    if resolved == REPO or REPO in resolved.parents:
        raise CheckFailed("refused: the folder must be outside the repo")
    if folder.exists():
        raise CheckFailed("refused: the folder must not exist yet")


def members(target: Path) -> Iterator[tuple[str, bytes]]:
    """Each member of an .apk or .zip, read with no extraction, or each file of a
    folder, as (name, bytes). Symlinks are skipped."""
    if guards.is_sealed(target):
        raise CheckFailed("refused: a path inside a folder named sealed")
    if target.is_file() and target.suffix.lower() in (".apk", ".zip"):
        with zipfile.ZipFile(target) as archive:
            for info in archive.infolist():
                if not info.is_dir():
                    yield info.filename, archive.read(info)
        return
    for path in sorted(target.rglob("*")):
        if path.is_file() and not path.is_symlink():
            yield path.relative_to(target).as_posix(), path.read_bytes()


def exact_hits(
    items: Iterable[tuple[str, bytes]], secrets: Mapping[str, bytes]
) -> dict[str, list[str]]:
    """Each secret's name, with the members that hold its bytes or their UTF-16LE form."""
    forms = {
        name: (value, value.decode("utf-8").encode("utf-16-le"))
        for name, value in secrets.items()
        if value
    }
    hits: dict[str, list[str]] = {}
    for member, data in items:
        for name, found in forms.items():
            if any(form in data for form in found):
                hits.setdefault(name, []).append(member)
    return hits


def marker_hits(
    items: Iterable[tuple[str, bytes]], markers: tuple[bytes, ...] = MARKERS
) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for member, data in items:
        for marker in markers:
            if marker in data:
                hits.setdefault(marker.decode(), []).append(member)
    return hits


def twelve_digit_lines(items: Iterable[tuple[str, bytes]]) -> list[str]:
    """`member:line` for each line with a 12-digit run, in members that decode as
    UTF-8, after hex runs of 32 or more are removed (check_account_ids.mjs's rule)."""
    found = []
    for member, data in items:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if _TWELVE.search(_LONG_HEX.sub("", line)):
                found.append(f"{member}:{n}")
    return found


def unpack(apk: Path, into: Path) -> Path:
    """The APK's members under `into`, a new folder outside the repo. A member with `..`,
    an absolute path or a drive is refused before anything is written."""
    _outside_the_repo(into)
    with zipfile.ZipFile(apk) as archive:
        names = [info.filename for info in archive.infolist()]
        for name in names:
            path = PurePosixPath(name.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or re.match(r"[A-Za-z]:", name):
                raise CheckFailed(
                    "refused: an APK member names a path outside its folder"
                )
        into.mkdir(parents=True)
        archive.extractall(into)
    return into


def shown(text: str, hide: Iterable[str] = ()) -> str:
    """`text` with each hidden value masked, then report ids and 12-digit runs."""
    for value in hide:
        if value:
            text = text.replace(value, "<secret>")
    return scrub(text)


def gitleaks_dir(folder: Path, hide: Iterable[str] = ()) -> int:
    """gitleaks over the folder, its output printed masked; its exit code."""
    done = subprocess.run(
        ["gitleaks", "dir", "--redact", "--no-banner", str(folder)],
        capture_output=True,
        text=True,
        check=False,
    )
    hide = tuple(hide)
    for line in (done.stdout + done.stderr).splitlines():
        if line.strip():
            say(shown(line, hide))
    return done.returncode


def apk_flags(apk: Path, aapt2: Path) -> dict:
    """allowBackup, the permissions and Capacitor's loggingBehavior, from aapt2's dump
    of the manifest and the APK's assets/capacitor.config.json."""
    dump = subprocess.run(
        [str(aapt2), "dump", "xmltree", "--file", "AndroidManifest.xml", str(apk)],
        capture_output=True,
        text=True,
        check=False,
    )
    if dump.returncode != 0:
        raise CheckFailed(f"aapt2 couldn't read the manifest (exit {dump.returncode})")
    allow_backup, permissions, element = None, [], ""
    for line in dump.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("E: "):
            element = stripped[3:].split(" ", 1)[0]
        elif stripped.startswith(f"A: {_ANDROID}"):
            match = re.match(rf"A: {re.escape(_ANDROID)}(\w+)\([^)]*\)=(\S+)", stripped)
            if match is None:
                continue
            name, value = match.groups()
            if element.startswith("uses-permission") and name == "name":
                permissions.append(value.strip('"'))
            elif element == "application" and name == "allowBackup":
                allow_backup = value.strip('"').lower() in ("true", "0xffffffff", "-1")
    with zipfile.ZipFile(apk) as archive:
        try:
            capacitor = json.loads(archive.read("assets/capacitor.config.json"))
        except (KeyError, ValueError):
            capacitor = {}
    return {
        "allowBackup": True
        if allow_backup is None
        else allow_backup,  # Android's default is true
        "permissions": sorted(permissions),
        "loggingBehavior": capacitor.get("loggingBehavior"),
    }


def flag_problems(flags: dict) -> list[str]:
    problems = []
    if flags["allowBackup"]:
        problems.append("allowBackup is true")
    outside = sorted(set(flags["permissions"]) - ALLOWED_PERMISSIONS)
    if outside:
        problems.append(f"permissions outside the allowed list: {', '.join(outside)}")
    if flags["loggingBehavior"] != "none":
        problems.append(f"loggingBehavior is {flags['loggingBehavior']!r}, not none")
    return problems


def fetch_site(url: str, into: Path, http: httpx.Client) -> Path:
    """The deployed index.html and the same-origin assets it, and each fetched script
    and stylesheet, names, into `into`, a new folder outside the repo."""
    _outside_the_repo(into)
    origin = urlparse(url)
    into.mkdir(parents=True)
    queue, seen = [urljoin(url, "/")], set()
    while queue and len(seen) < MAX_SITE_FILES:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        response = http.get(current)
        if response.status_code != 200:
            continue
        path = urlparse(current).path
        relative = PurePosixPath(path.lstrip("/") or "index.html")
        if ".." in relative.parts:
            continue
        target = into / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        if relative.suffix in ("", ".html", ".js", ".css", ".mjs"):
            for groups in _LINKS.findall(response.content):
                link = next((g for g in groups if g), b"").decode("utf-8", "replace")
                found = urlparse(urljoin(current, link))
                if found.scheme in ("http", "https") and found.netloc == origin.netloc:
                    queue.append(found._replace(query="", fragment="").geturl())
    return into


def load_secrets(
    session=None, environ: Mapping[str, str] | None = None
) -> dict[str, bytes]:
    """The Meta key, from MODEL_API_KEY, and the account ID, from sts; never printed."""
    env = os.environ if environ is None else environ
    key = env.get("MODEL_API_KEY", "")
    if not key:
        raise CheckFailed(
            "refused: MODEL_API_KEY isn't set, so the key can't be looked for"
        )
    account = (
        (session or lusot_session()).client("sts").get_caller_identity()["Account"]
    )
    return {"meta_key": key.encode(), "account_id": account.encode()}


def main(
    argv: Sequence[str] | None = None, *, session=None, http: httpx.Client | None = None
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "target", nargs="?", type=Path, help="an APK, a zip or a folder"
    )
    parser.add_argument("--aapt2", type=Path, help="aapt2, for an APK's manifest")
    parser.add_argument("--site", help="the deployed site's URL, fetched first")

    def command() -> int:
        args = parser.parse_args(argv)
        if (args.target is None) == (args.site is None):
            parser.error("give an APK or folder, or --site URL")
        try:
            found = load_secrets(session)
            hide = tuple(value.decode() for value in found.values())
            stamp = datetime.now(PHT).strftime("%Y-%m-%d-%H%M%S")
            if args.site:
                client = http if http is not None else ipv4_client()
                target = fetch_site(
                    args.site, data_dir() / "ms7" / f"site-{stamp}", client
                )
            else:
                target = args.target
            items = list(members(target))
            is_apk = target.is_file() and target.suffix.lower() == ".apk"
            scanned = (
                unpack(target, data_dir() / "ms7" / f"apk-{stamp}")
                if is_apk
                else target
            )
        except CheckFailed as exc:
            say(str(exc))
            return 2
        problems = []
        for name, where in exact_hits(items, found).items():
            problems.append(
                f"{name} found in {', '.join(shown(m, hide) for m in where)}"
            )
        for marker, where in marker_hits(items).items():
            problems.append(
                f"{marker} found in {', '.join(shown(m, hide) for m in where)}"
            )
        problems += [
            f"a 12-digit run at {shown(spot, hide)}"
            for spot in twelve_digit_lines(items)
        ]
        leaks = gitleaks_dir(scanned, hide)
        if leaks:
            problems.append(f"gitleaks exited {leaks}")
        if is_apk:
            if args.aapt2 is None:
                problems.append("no --aapt2, so the manifest wasn't checked")
            else:
                problems += flag_problems(apk_flags(target, args.aapt2))
        say(f"scanned {len(items)} members")
        for problem in problems:
            say(f"FAIL: {problem}")
        say(
            f"BUILD SCAN FAILED: {len(problems)} findings"
            if problems
            else "BUILD SCAN OK"
        )
        return 1 if problems else 0

    return guarded(
        command, label="BUILD SCAN FAILED", errors=(httpx.HTTPError, zipfile.BadZipFile)
    )


if __name__ == "__main__":
    raise SystemExit(main())
