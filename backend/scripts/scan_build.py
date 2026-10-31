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
  binary ones such as classes.dex and resources.arsc included (Review Focus 5), or in a
  member's name
- a marker that only a wrong build carries: api.meta.ai, MODEL_API_KEY, the mock API's
  LUSOT_MOCK_API, or an end-to-end fixture's LUSOT_E2E_FIXTURE (MS5's check-bundle.mjs)
- a 12-digit run in a member's name, or in a member that decodes as UTF-8, once hex runs
  of 32 or more are removed, as scripts/check_account_ids.mjs reads it
- gitleaks' own findings, under the repo's .gitleaks.toml, over the APK or zip unpacked
  into a fresh folder outside the repo, which is deleted afterwards
- for an APK, through aapt2: allowBackup not a literal false, a permission outside
  ALLOWED_PERMISSIONS, or a loggingBehavior other than none in
  assets/capacitor.config.json (its android override included)

--site URL first fetches the deployed index.html and the same-origin assets that it,
its scripts, stylesheets, manifests and JSON name into a fresh folder under
LUSOT_DATA_DIR\\ms7\\, and scans that, so the scan reads what judges download, not a
rebuild. A root that doesn't answer 200, or a scan that read no member, refuses (exit 2);
a crawl that hits its cap fails.

A folder under the target named sealed is refused before it is read. The key comes from
MODEL_API_KEY and the account ID from sts, inside the run; neither is ever printed.
Findings name the secret and the member, with each secret's text, any 12-digit run and
the scratch folder's path masked.

Usage: uv run backend/scripts/scan_build.py <apk, zip or folder> [--aapt2 PATH]
       uv run backend/scripts/scan_build.py --site URL
Exit codes: 0 nothing found; 1 a finding; 2 refused (a sealed or in-repo folder, a
target that isn't an APK, a zip or a folder, nothing scanned, a missing secret, or bad
usage).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import zipfile
from collections.abc import Iterable, Iterator, Mapping, Sequence
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urljoin, urlparse

import guards
import httpx
from botocore.exceptions import BotoCoreError, ClientError
from harden import data_dir, ipv4_client, say, scrub
from ops_common import PHT, guarded, lusot_session
from smoke_upload import CheckFailed

REPO = Path(__file__).resolve().parents[2]
GITLEAKS_CONFIG = REPO / ".gitleaks.toml"
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
        # Ask Lusot's voice (its spec §4.7, C718), in the APK since ask-app merged: Capacitor's
        # WebView client asks for both when the page opens the microphone.
        "android.permission.RECORD_AUDIO",
        "android.permission.MODIFY_AUDIO_SETTINGS",
    }
)
# MS5's check-bundle.mjs:10, the same four.
MARKERS = (b"api.meta.ai", b"MODEL_API_KEY", b"LUSOT_MOCK_API", b"LUSOT_E2E_FIXTURE")
MAX_SITE_FILES = 500
ARCHIVES = (".apk", ".zip")
_LONG_HEX = re.compile(r"(?<![0-9a-f])[0-9a-f]{32,}(?![0-9a-f])", re.IGNORECASE)
_TWELVE = re.compile(r"(?<![0-9])[0-9]{12}(?![0-9])")
_ASSET = r"(?:m?js|css|json|txt|png|svg|webp|jpe?g|ico|woff2?|webmanifest)"
# An attribute's link, a stylesheet's url(), or a quoted path a script, manifest or JSON
# names: "./chunk-x.js", "/assets/x.js", or Vite's base-relative "assets/x.js".
_LINKS = re.compile(
    rb"""(?:src|href)\s*=\s*["']([^"']+)["']|url\(\s*["']?([^"')]+)["']?\s*\)"""
    rb"""|["']((?:\.{0,2}/)?[A-Za-z0-9_][A-Za-z0-9_./-]*\."""
    + _ASSET.encode()
    + rb""")["']"""
)
_PARSED = ("", ".html", ".js", ".mjs", ".css", ".json", ".webmanifest")
_ANDROID = "http://schemas.android.com/apk/res/android:"


def _new_folder_outside_the_repo(folder: Path) -> None:
    if guards.is_sealed(folder):
        raise CheckFailed("refused: a path inside a folder named sealed")
    resolved = folder.resolve()
    if resolved == REPO or REPO in resolved.parents:
        raise CheckFailed("refused: the folder must be outside the repo")
    if folder.exists():
        raise CheckFailed("refused: the folder must not exist yet")


def members(target: Path) -> Iterator[tuple[str, bytes]]:
    """Each member of an .apk or .zip, read with no extraction, or each file of a
    folder, as (name, bytes). Symlinks are skipped, and a folder named sealed below the
    target is refused before anything in it is listed."""
    if guards.is_sealed(target):
        raise CheckFailed("refused: a path inside a folder named sealed")
    if target.is_file() and target.suffix.lower() in ARCHIVES:
        with zipfile.ZipFile(target) as archive:
            for info in archive.infolist():
                if not info.is_dir():
                    yield info.filename, archive.read(info)
        return
    if not target.is_dir():
        raise CheckFailed("refused: the target must be an APK, a zip or a folder")
    for root, dirs, files in os.walk(target):
        here = Path(root)
        for name in sorted(dirs):
            if guards.is_sealed(here / name):
                raise CheckFailed("refused: the folder holds a folder named sealed")
        dirs[:] = sorted(d for d in dirs if not (here / d).is_symlink())
        for name in sorted(files):
            path = here / name
            if not path.is_symlink():
                yield path.relative_to(target).as_posix(), path.read_bytes()


def exact_hits(
    items: Iterable[tuple[str, bytes]], secrets: Mapping[str, bytes]
) -> dict[str, list[str]]:
    """Each secret's name, with the members whose bytes or name hold its bytes or their
    UTF-16LE form."""
    forms = {
        name: (value, value.decode("utf-8").encode("utf-16-le"))
        for name, value in secrets.items()
        if value
    }
    hits: dict[str, list[str]] = {}
    for member, data in items:
        named = member.encode("utf-8", "replace")
        for name, found in forms.items():
            if any(form in data for form in found) or found[0] in named:
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
    UTF-8, after hex runs of 32 or more are removed (check_account_ids.mjs's rule), and
    `member:name` for a member whose name holds one."""
    found = []
    for member, data in items:
        if _TWELVE.search(_LONG_HEX.sub("", member)):
            found.append(f"{member}:name")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if _TWELVE.search(_LONG_HEX.sub("", line)):
                found.append(f"{member}:{n}")
    return found


def unpack(apk: Path, into: Path) -> Path:
    """The archive's members under `into`, a new folder outside the repo. A member with
    `..`, an absolute path or a drive is refused before anything is written."""
    _new_folder_outside_the_repo(into)
    with zipfile.ZipFile(apk) as archive:
        for info in archive.infolist():
            name = info.filename
            path = PurePosixPath(name.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or re.match(r"[A-Za-z]:", name):
                raise CheckFailed(
                    "refused: an archive member names a path outside its folder"
                )
        into.mkdir(parents=True)
        archive.extractall(into)
    return into


def shown(text: str, hide: Iterable[str] = ()) -> str:
    """`text` with each hidden value masked, then report ids and 12-digit runs."""
    for value in hide:
        if value:
            text = text.replace(value, "<hidden>")
    return scrub(text)


def gitleaks_dir(folder: Path, hide: Iterable[str] = ()) -> int:
    """gitleaks over the folder, under the repo's own config and no other, its output
    printed with the hidden values and the folder's path masked; its exit code."""
    env = {k: v for k, v in os.environ.items() if k != "GITLEAKS_CONFIG"}
    done = subprocess.run(
        [
            "gitleaks",
            "dir",
            "--redact",
            "--no-banner",
            "--verbose",
            "--config",
            str(GITLEAKS_CONFIG),
            "--max-archive-depth",
            "2",
            str(folder),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    hide = (*tuple(hide), str(folder.resolve()), str(folder))
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
                # Only a literal false passes: a resource reference could be anything.
                allow_backup = value.strip('"').lower() not in ("false", "0x0")
    with zipfile.ZipFile(apk) as archive:
        try:
            capacitor = json.loads(archive.read("assets/capacitor.config.json"))
        except (KeyError, ValueError):
            capacitor = {}
    android = (
        capacitor.get("android") if isinstance(capacitor.get("android"), dict) else {}
    )
    return {
        "allowBackup": True
        if allow_backup is None
        else allow_backup,  # Android's default is true
        "permissions": sorted(permissions),
        "loggingBehavior": android.get(
            "loggingBehavior", capacitor.get("loggingBehavior")
        ),
    }


def flag_problems(flags: dict) -> list[str]:
    problems = []
    if flags["allowBackup"]:
        problems.append("allowBackup isn't a literal false")
    outside = sorted(set(flags["permissions"]) - ALLOWED_PERMISSIONS)
    if outside:
        problems.append(f"permissions outside the allowed list: {', '.join(outside)}")
    if flags["loggingBehavior"] != "none":
        problems.append(f"loggingBehavior is {flags['loggingBehavior']!r}, not none")
    return problems


def _resolve(link: str, current: str, root: str) -> str:
    """A link's URL: one starting with a scheme, `/`, `./` or `../` against the page that
    names it; a bare path, such as Vite's "assets/x.js", against the site's root."""
    if re.match(r"[a-z][a-z0-9+.-]*:|/|\./|\.\./", link):
        return urljoin(current, link)
    return urljoin(root, link)


def fetch_site(url: str, into: Path, http: httpx.Client) -> tuple[Path, dict[str, int]]:
    """The deployed index.html and the same-origin assets that it and each fetched
    script, stylesheet, manifest and JSON name, into `into`, a new folder outside the
    repo. It returns the folder and counts: files saved, named paths that didn't answer
    200, and paths left when the cap was reached. A root that isn't 200 refuses."""
    _new_folder_outside_the_repo(into)
    origin = urlparse(url)
    root = urljoin(url, "/")
    into.mkdir(parents=True)
    base = into.resolve()
    queue, seen = [root], set()
    counts = {"saved": 0, "missing": 0, "left": 0}
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        if len(seen) >= MAX_SITE_FILES:
            counts["left"] = len(set(queue) - seen) + 1
            break
        seen.add(current)
        response = http.get(current)
        if response.status_code != 200:
            if current == root:
                raise CheckFailed(
                    f"refused: the site's root answered HTTP {response.status_code}"
                )
            counts["missing"] += 1
            continue
        # Decoded first, so an encoded backslash or drive is refused like a plain one.
        relative = PurePosixPath(
            unquote(urlparse(current).path).lstrip("/") or "index.html"
        )
        parts = relative.parts
        if any(
            p in ("..", ".") or "\\" in p or ":" in p for p in parts
        ) or guards.is_sealed(Path(*parts)):
            counts["missing"] += 1
            continue
        target = (into / Path(*parts)).resolve()
        if base not in target.parents:
            counts["missing"] += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        counts["saved"] += 1
        if relative.suffix in _PARSED:
            for groups in _LINKS.findall(response.content):
                link = next((g for g in groups if g), b"").decode("utf-8", "replace")
                found = urlparse(_resolve(link, current, root))
                if found.scheme == origin.scheme and found.netloc == origin.netloc:
                    queue.append(found._replace(query="", fragment="").geturl())
    return into, counts


def load_secrets(
    session=None, environ: Mapping[str, str] | None = None
) -> dict[str, bytes]:
    """The Meta key, from MODEL_API_KEY, and the account ID, from sts; never printed."""
    env = os.environ if environ is None else environ
    key = env.get("MODEL_API_KEY", "").strip()
    if not key:
        raise CheckFailed(
            "refused: MODEL_API_KEY isn't set, so the key can't be looked for"
        )
    account = (
        (session or lusot_session())
        .client("sts")
        .get_caller_identity()
        .get("Account", "")
    )
    if not account:
        raise CheckFailed("refused: sts gave no account ID, so it can't be looked for")
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
            parser.error("give an APK, a zip or a folder, or --site URL")
        problems: list[str] = []
        unpacked: Path | None = None
        try:
            found = load_secrets(session)
            stamp = datetime.now(PHT).strftime("%Y-%m-%d-%H%M%S")
            if args.site:
                client = http if http is not None else ipv4_client()
                target, counts = fetch_site(
                    args.site, data_dir() / "ms7" / f"site-{stamp}", client
                )
                say(
                    f"fetched {counts['saved']} files; {counts['missing']} named paths didn't answer 200"
                )
                if counts["left"]:
                    problems.append(
                        f"the crawl stopped at {MAX_SITE_FILES} files, with {counts['left']} left"
                    )
            else:
                target = args.target
            items = list(members(target))
            if not items:
                raise CheckFailed("refused: no member was read, so nothing was scanned")
            archive = target.is_file() and target.suffix.lower() in ARCHIVES
            if archive:
                unpacked = unpack(target, data_dir() / "ms7" / f"unpacked-{stamp}")
            hide = (*(value.decode() for value in found.values()), str(target))
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
            leaks = gitleaks_dir(unpacked or target, hide)
            if leaks:
                problems.append(f"gitleaks exited {leaks}")
            if archive and target.suffix.lower() == ".apk":
                if args.aapt2 is None:
                    problems.append("no --aapt2, so the manifest wasn't checked")
                else:
                    try:
                        problems += flag_problems(apk_flags(target, args.aapt2))
                    except CheckFailed as exc:
                        problems.append(str(exc))
        except CheckFailed as exc:
            say(str(exc))
            return 2
        finally:
            if unpacked is not None:
                shutil.rmtree(
                    unpacked, ignore_errors=True
                )  # C813: unpacked, scanned, deleted
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
        command,
        label="BUILD SCAN FAILED",
        shown=(CheckFailed,),
        errors=(httpx.HTTPError, zipfile.BadZipFile, BotoCoreError, ClientError),
    )


if __name__ == "__main__":
    raise SystemExit(main())
