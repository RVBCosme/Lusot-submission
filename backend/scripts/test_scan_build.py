"""Tests for scan_build.py: the APK and web-bundle scan (MS7 plan Task 6, C813).

Every secret is built at run time: the key with secrets.token_urlsafe(36), the account
ID as 12 random digits. gitleaks_dir is replaced in every unit test, since CI's Python
job has no gitleaks; the one test that runs the real gitleaks is skipped without it.
httpx's MockTransport answers the site fetch. Nothing reaches AWS or a Lusot endpoint,
and no folder named sealed is made.

check:py runs this file with the scripts' dependencies. Alone, from the repo root:
    uv run --python 3.13 --with pytest --with boto3 --with httpx --with numpy
        --with "opencv-python-headless<5" pytest -q backend/scripts/test_scan_build.py
"""

import json
import random
import secrets
import shutil
import string
import zipfile
from pathlib import Path

import httpx
import pytest
import scan_build
from smoke_upload import CheckFailed
from stubs import StubSession

REPO = Path(__file__).resolve().parents[2]
RECEIVER = "io.github.rvbcosme.lusot.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION"


@pytest.fixture
def made():
    key = secrets.token_urlsafe(36)
    account = "".join(random.choice("0123456789") for _ in range(12))
    return {"meta_key": key.encode(), "account_id": account.encode()}


@pytest.fixture(autouse=True)
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("LUSOT_DATA_DIR", str(tmp_path / "data"))


def apk(path: Path, files: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return path


def config(logging="none") -> bytes:
    return json.dumps(
        {"appId": "io.github.rvbcosme.lusot", "loggingBehavior": logging}
    ).encode()


def test_exact_bytes_found_in_a_binary_member(tmp_path, made):
    dex = random.randbytes(2000) + made["meta_key"] + random.randbytes(500)
    target = apk(tmp_path / "app.apk", {"classes.dex": dex, "assets/x.txt": b"plain"})
    hits = scan_build.exact_hits(scan_build.members(target), made)
    assert hits == {"meta_key": ["classes.dex"]}


def test_utf16_secret_is_found(tmp_path, made):
    arsc = b"\x02\x00" + made["meta_key"].decode().encode("utf-16-le") + b"\x00\x00"
    target = apk(tmp_path / "app.apk", {"resources.arsc": arsc})
    assert scan_build.exact_hits(scan_build.members(target), made) == {
        "meta_key": ["resources.arsc"]
    }


def test_output_never_holds_the_secret(tmp_path, made, monkeypatch, capsys):
    key, account = made["meta_key"].decode(), made["account_id"].decode()
    target = apk(
        tmp_path / "app.apk",
        {
            "classes.dex": b"\x00" + made["meta_key"] + b"\x00",
            f"assets/{key}.txt": b"named after the key",
            f"assets/{account}.json": b"{}",
            "assets/public/app.js": f"const id = '{account}'".encode(),
            "assets/capacitor.config.json": config(),
        },
    )
    monkeypatch.setattr(scan_build, "load_secrets", lambda session=None: made)
    monkeypatch.setattr(scan_build, "gitleaks_dir", lambda folder, hide=(): 0)
    monkeypatch.setattr(
        scan_build,
        "apk_flags",
        lambda path, aapt2: {
            "allowBackup": False,
            "permissions": ["android.permission.INTERNET"],
            "loggingBehavior": "none",
        },
    )
    assert scan_build.main([str(target), "--aapt2", "aapt2"]) == 1
    out = capsys.readouterr().out
    assert key not in out and account not in out
    assert "meta_key" in out and "account_id" in out  # what was found, by name
    assert "assets/<hidden>.txt" in out  # the member named after the key, masked


def test_markers_in_any_file(tmp_path):
    target = apk(
        tmp_path / "app.apk",
        {
            "assets/public/x.js": b"fetch('https://api.meta.ai/v1')",
            "classes2.dex": random.randbytes(64)
            + b"api.meta.ai"
            + random.randbytes(64),
            "assets/public/y.js": b"const m = 'LUSOT_MOCK_API'",
            "assets/public/z.js": b"clean",
        },
    )
    hits = scan_build.marker_hits(scan_build.members(target))
    assert hits == {
        "api.meta.ai": ["assets/public/x.js", "classes2.dex"],
        "LUSOT_MOCK_API": ["assets/public/y.js"],
    }


def test_twelve_digit_runs_skip_long_hex(tmp_path):
    twelve = "".join(random.choice("0123456789") for _ in range(12))
    hexrun = "".join(random.choice("0123456789abcdef") for _ in range(20)) + twelve
    folder = tmp_path / "site"
    folder.mkdir()
    (folder / "a.js").write_text(f"x\nconst hash = '{hexrun}'\nconst y = 1\n")
    (folder / "b.js").write_text(f"one\ntwo {twelve}\n")
    (folder / "c.bin").write_bytes(b"\xff\xfe" + twelve.encode())  # not UTF-8: skipped
    (folder / "d.js").write_text(f"{twelve}3 is thirteen\n")
    assert scan_build.twelve_digit_lines(scan_build.members(folder)) == ["b.js:2"]


def test_unpack_refuses_traversal_and_the_repo(tmp_path):
    good = apk(tmp_path / "good.apk", {"assets/a.txt": b"a"})
    into = tmp_path / "out"
    assert (scan_build.unpack(good, into) / "assets" / "a.txt").read_bytes() == b"a"
    with pytest.raises(CheckFailed):
        scan_build.unpack(good, into)  # must not exist
    for bad in ("../escape.txt", "/abs.txt", "C:/drive.txt"):
        evil = apk(tmp_path / f"evil{len(bad)}.apk", {bad: b"x"})
        with pytest.raises(CheckFailed):
            scan_build.unpack(evil, tmp_path / f"o{len(bad)}")
        assert not (tmp_path / f"o{len(bad)}").exists()
    with pytest.raises(CheckFailed):
        scan_build.unpack(good, REPO / "unpacked-apk")
    assert not (REPO / "unpacked-apk").exists()
    with pytest.raises(CheckFailed):
        scan_build.unpack(good, tmp_path / "sealed" / "x")
    with pytest.raises(CheckFailed):
        list(scan_build.members(tmp_path / "sealed" / "app.apk"))
    assert not (tmp_path / "sealed").exists()


def xmltree(allow_backup: str, permissions: list[str]) -> str:
    """aapt2 dump xmltree's text for a manifest, as the test builds it."""
    rows = [
        "N: android=http://schemas.android.com/apk/res/android (line=2)",
        "  E: manifest (line=2)",
    ]
    for permission in permissions:
        rows += [
            "    E: uses-permission (line=43)",
            f'      A: http://schemas.android.com/apk/res/android:name(0x01010003)="{permission}" (Raw: "{permission}")',
        ]
    rows += [
        "    E: application (line=5)",
        f"      A: http://schemas.android.com/apk/res/android:allowBackup(0x01010280)={allow_backup}",
        '      A: http://schemas.android.com/apk/res/android:label(0x01010001)="Lusot"',
    ]
    return "\n".join(rows) + "\n"


def test_apk_flags_parsed(tmp_path, monkeypatch):
    target = apk(
        tmp_path / "app.apk",
        {"assets/capacitor.config.json": config(), "AndroidManifest.xml": b"\x03\x00"},
    )
    allowed = ["android.permission.INTERNET", "android.permission.CAMERA", RECEIVER]

    def dumped(allow_backup, permissions):
        def run(command, **kwargs):
            assert command[1:4] == ["dump", "xmltree", "--file"]
            return type(
                "Done",
                (),
                {
                    "returncode": 0,
                    "stdout": xmltree(allow_backup, permissions),
                    "stderr": "",
                },
            )()

        monkeypatch.setattr(scan_build.subprocess, "run", run)
        return scan_build.apk_flags(target, Path("aapt2"))

    flags = dumped("false", allowed)
    assert flags == {
        "allowBackup": False,
        "permissions": sorted(allowed),
        "loggingBehavior": "none",
    }
    assert (
        scan_build.flag_problems(flags) == []
    )  # the AndroidX receiver permission passes
    assert len(scan_build.flag_problems(dumped("true", allowed))) == 1
    assert len(scan_build.flag_problems(dumped("0xffffffff", allowed))) == 1
    outside = dumped("false", [*allowed, "android.permission.READ_CONTACTS"])
    assert len(scan_build.flag_problems(outside)) == 1
    noisy = apk(
        tmp_path / "noisy.apk", {"assets/capacitor.config.json": config("debug")}
    )
    monkeypatch.setattr(
        scan_build.subprocess,
        "run",
        lambda command, **kw: type(
            "Done",
            (),
            {"returncode": 0, "stdout": xmltree("false", allowed), "stderr": ""},
        )(),
    )
    assert (
        len(scan_build.flag_problems(scan_build.apk_flags(noisy, Path("aapt2")))) == 1
    )


def test_fetch_site_stays_on_its_origin(tmp_path):
    asked = []
    pages = {
        "/": b'<html><script type="module" src="/assets/index-a1.js"></script>'
        b'<link rel="stylesheet" href="/assets/index-b2.css"><link rel="icon" href="icons/i.png">'
        b'<link rel="manifest" href="/manifest.webmanifest">'
        b'<script src="https://other.test.invalid/tracker.js"></script>'
        b'<a href="//other.test.invalid/x.js">x</a><a href="http://site.test.invalid/plain.js">p</a>'
        b'<a href="/assets/..%5C..%5Cevil.js">e</a><a href="/missing.js">m</a></html>',
        "/assets/index-a1.js": b'import("./chunk-c3.js"); const u = "/assets/chunk-d4.js";'
        b' const deps = ["assets/lazy-f6.js"]; fetch("./licences.txt");',
        "/assets/index-b2.css": b"body { background: url(/assets/bg-e5.png) }",
        "/assets/chunk-c3.js": b"chunk c3",
        "/assets/chunk-d4.js": b"chunk d4",
        "/assets/lazy-f6.js": b"lazy f6",
        "/assets/licences.txt": b"licences",
        "/assets/bg-e5.png": b"png",
        "/icons/i.png": b"icon",
        "/manifest.webmanifest": b'{"icons": [{"src": "icons/m-192.png"}]}',
        "/icons/m-192.png": b"manifest icon",
        "/assets/..\\..\\evil.js": b"traversal",
    }

    def handle(request):
        asked.append(str(request.url))
        body = (
            pages.get(request.url.path)
            if request.url.host == "site.test.invalid"
            else None
        )
        return (
            httpx.Response(200, content=body)
            if body is not None
            else httpx.Response(404)
        )

    http = httpx.Client(transport=httpx.MockTransport(handle))
    into = tmp_path / "site"
    folder, counts = scan_build.fetch_site("https://site.test.invalid/", into, http)
    saved = sorted(
        p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()
    )
    assert saved == [
        "assets/bg-e5.png",
        "assets/chunk-c3.js",
        "assets/chunk-d4.js",
        "assets/index-a1.js",
        "assets/index-b2.css",
        "assets/lazy-f6.js",
        "assets/licences.txt",
        "icons/i.png",
        "icons/m-192.png",
        "index.html",
        "manifest.webmanifest",
    ]
    assert not any(
        "other.test.invalid" in url or url.startswith("http:") for url in asked
    )
    assert not (tmp_path / "evil.js").exists() and counts["missing"] >= 1
    assert counts["saved"] == 11 and counts["left"] == 0
    with pytest.raises(CheckFailed):
        scan_build.fetch_site(
            "https://site.test.invalid/", into, http
        )  # must not exist
    with pytest.raises(CheckFailed):
        scan_build.fetch_site("https://site.test.invalid/", REPO / "fetched-site", http)
    down = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(301))
    )
    with pytest.raises(CheckFailed, match="root"):
        scan_build.fetch_site("https://site.test.invalid/", tmp_path / "down", down)


def test_load_secrets_needs_both(monkeypatch):
    with pytest.raises(CheckFailed):
        scan_build.load_secrets(session=object(), environ={})
    session = StubSession("sts")
    session.stubs["sts"].add_response("get_caller_identity", {"UserId": "stub"})
    with pytest.raises(CheckFailed, match="account"):
        scan_build.load_secrets(
            session=session, environ={"MODEL_API_KEY": secrets.token_urlsafe(8)}
        )


@pytest.mark.skipif(shutil.which("gitleaks") is None, reason="gitleaks isn't installed")
def test_real_gitleaks_finds_a_key_and_prints_none(tmp_path, capsys):
    folder = tmp_path / "bundle"
    folder.mkdir()
    value = "".join(
        random.sample(string.ascii_letters + string.digits, 40)
    )  # sure entropy
    (folder / "config.js").write_text(f'const api_key = "{value}";\n')
    assert scan_build.gitleaks_dir(folder, hide=(value,)) == 1
    out = capsys.readouterr().out
    assert "REDACTED" in out  # --verbose prints the finding, redacted
    assert value not in out and str(folder) not in out


def test_nothing_scanned_or_a_wrong_target_refuses(tmp_path, made, monkeypatch, capsys):
    monkeypatch.setattr(scan_build, "load_secrets", lambda session=None: made)
    monkeypatch.setattr(scan_build, "gitleaks_dir", lambda folder, hide=(): 0)
    bundle = tmp_path / "app.aab"
    bundle.write_bytes(b"PK" + made["meta_key"])
    assert scan_build.main([str(bundle)]) == 2
    empty = tmp_path / "empty"
    empty.mkdir()
    assert scan_build.main([str(empty)]) == 2
    assert "refused" in capsys.readouterr().out


def test_a_folder_named_sealed_below_the_target_is_refused(tmp_path, monkeypatch):
    # A stand-in name: no folder named sealed is ever made.
    monkeypatch.setattr(
        scan_build.guards, "is_sealed", lambda path: Path(path).name == "locked"
    )
    target = tmp_path / "bundle"
    (target / "locked").mkdir(parents=True)
    (target / "locked" / "inside.txt").write_text("never read")
    (target / "a.txt").write_text("a")
    with pytest.raises(CheckFailed):
        list(scan_build.members(target))


def test_a_zip_is_unpacked_for_gitleaks_and_deleted(tmp_path, made, monkeypatch):
    seen = []

    def gitleaks(folder, hide=()):
        seen.append((folder, sorted(p.name for p in folder.rglob("*"))))
        return 0

    monkeypatch.setattr(scan_build, "load_secrets", lambda session=None: made)
    monkeypatch.setattr(scan_build, "gitleaks_dir", gitleaks)
    target = apk(tmp_path / "web.zip", {"index.html": b"<html></html>"})
    assert scan_build.main([str(target)]) == 0
    [(folder, names)] = seen
    assert names == ["index.html"] and not folder.exists()  # unpacked, scanned, deleted


def test_the_e2e_fixture_marker_and_android_overrides(tmp_path, monkeypatch):
    target = apk(
        tmp_path / "app.apk",
        {
            "assets/public/f.js": b"LUSOT_E2E_FIXTURE",
            "assets/capacitor.config.json": json.dumps(
                {"loggingBehavior": "none", "android": {"loggingBehavior": "debug"}}
            ).encode(),
        },
    )
    assert "LUSOT_E2E_FIXTURE" in scan_build.marker_hits(scan_build.members(target))
    allowed = ["android.permission.INTERNET"]
    monkeypatch.setattr(
        scan_build.subprocess,
        "run",
        lambda command, **kw: type(
            "Done",
            (),
            {"returncode": 0, "stdout": xmltree("@0x7f050000", allowed), "stderr": ""},
        )(),
    )
    flags = scan_build.apk_flags(target, Path("aapt2"))
    assert flags["allowBackup"] is True  # a resource reference isn't a literal false
    assert flags["loggingBehavior"] == "debug"  # the android override wins
    assert len(scan_build.flag_problems(flags)) == 2


def test_the_repo_manifest_asks_only_for_allowed_permissions():
    """The decided default (Task 6): the APK's permissions stay a subset of
    ALLOWED_PERMISSIONS, so the source manifest's own must be inside it. Ask Lusot's
    voice adds RECORD_AUDIO and MODIFY_AUDIO_SETTINGS, which Capacitor's WebView client
    asks for together."""
    import xml.etree.ElementTree as ET

    manifest = REPO / "app" / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
    name = "{http://schemas.android.com/apk/res/android}name"
    declared = {
        element.get(name) for element in ET.parse(manifest).getroot().iter("uses-permission")
    }
    assert "android.permission.RECORD_AUDIO" in declared
    assert declared <= scan_build.ALLOWED_PERMISSIONS, sorted(
        declared - scan_build.ALLOWED_PERMISSIONS
    )
