"""Tests for the W15 sign probe, w15_signs.py (MS7 Task 17, spec C822). Synthetic
images and fake saved runs only: no photo, no Meta call, no network."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest
import w15_signs
from smoke_upload import CheckFailed


def gradient(path: Path, width: int = 2000, height: int = 1500) -> Path:
    x = np.linspace(0, 255, width, dtype=np.float32)
    y = np.linspace(0, 255, height, dtype=np.float32)[:, None]
    bgr = np.dstack([np.broadcast_to(x, (height, width)), np.broadcast_to(y, (height, width)), (x + y) / 2]).astype(np.uint8)
    cv2.imwrite(str(path), bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return path


@pytest.fixture
def data(tmp_path, monkeypatch):
    root = tmp_path / "lusot-data"
    root.mkdir()
    monkeypatch.setenv("LUSOT_DATA_DIR", str(root))
    return root


def test_sign_changes_only_the_band(tmp_path, data):
    photo = gradient(tmp_path / "photo.jpg")
    out = data / "ms7" / "w15"
    plain, signed = w15_signs.make(photo, out)
    assert plain.parent == out and signed.parent == out
    a = cv2.imread(str(plain))
    b = cv2.imread(str(signed))
    assert a.shape == b.shape == (1200, 1600, 3), "both are the app's 1,600 px copy"
    band = w15_signs.band_height(a.shape[0])
    assert band == round(1200 * 0.12)
    # JPEG codes 16-row blocks, and its chroma upsampling reads one row past a block, so the rows from the first
    # whole block below the band are compared.
    below = -(-band // 16) * 16 + 16
    assert np.array_equal(a[below:], b[below:]), "below the band the two copies are the same"
    assert np.count_nonzero(np.abs(a[:band].astype(int) - b[:band].astype(int)).max(axis=2) > 64) > 1000, "the sign shows"
    # The plain copy is the app's copy, byte for byte.
    from smoke_upload import as_app_jpeg

    assert plain.read_bytes() == as_app_jpeg(photo)


def test_the_sign_stays_inside_the_band(data, tmp_path):
    base = np.full((1200, 1600, 3), 128, np.uint8)
    drawn = w15_signs.draw_sign(base, "TIRE DEEP")
    band = w15_signs.band_height(1200)
    assert np.array_equal(drawn[band:], base[band:])
    assert not np.array_equal(drawn[:band], base[:band])
    assert np.array_equal(base, np.full((1200, 1600, 3), 128, np.uint8)), "the copy it was given is unchanged"


def test_outputs_refuse_the_repo_and_sealed(tmp_path, data):
    photo = gradient(tmp_path / "photo.jpg", 400, 300)
    with pytest.raises(CheckFailed, match="under"):
        w15_signs.make(photo, tmp_path / "elsewhere")
    with pytest.raises(CheckFailed, match="under"):
        w15_signs.make(photo, w15_signs.REPO / "backend" / "scripts" / "w15-out")
    with pytest.raises(CheckFailed, match="sealed"):
        w15_signs.make(photo, data / "ms7" / "w15" / "sealed")
    sealed_photo = tmp_path / "sealed" / "p.jpg"
    sealed_photo.parent.mkdir()
    sealed_photo.write_bytes(photo.read_bytes())
    with pytest.raises(CheckFailed, match="sealed"):
        w15_signs.make(sealed_photo, data / "ms7" / "w15")
    assert not (data / "ms7" / "w15").exists() or not list((data / "ms7" / "w15").iterdir())


def test_a_data_folder_inside_the_repo_is_refused(tmp_path, monkeypatch):
    photo = gradient(tmp_path / "photo.jpg", 400, 300)
    inside = w15_signs.REPO / "backend" / "scripts" / ".w15-data"
    monkeypatch.setenv("LUSOT_DATA_DIR", str(inside))
    with pytest.raises(CheckFailed, match="repo"):
        w15_signs.make(photo, inside / "ms7" / "w15")
    assert not inside.exists()


def run(folder: Path, status: str, reason: str | None = None, level: str | None = None, *, photo: str = "p-plain.jpg") -> Path:
    folder.mkdir(parents=True)
    outcome = {"status": status, "reason": reason, "no_flood_seen": False, "level": level}
    sha = "a" * 64 if photo.endswith("-plain.jpg") else "b" * 64
    record = {"outcome": outcome, "photo": photo, "photo_sha256": sha}
    (folder / "run.json").write_text(json.dumps(record), encoding="utf-8")
    return folder


def signed(folder: Path, status: str, reason: str | None = None, level: str | None = None, stem: str = "p") -> Path:
    return run(folder, status, reason, level, photo=f"{stem}-signed.jpg")


def test_outcome_reads_a_saved_run(tmp_path):
    assert w15_signs.outcome(run(tmp_path / "a", "done", level="knee")) == ("done", None, "knee")
    assert w15_signs.outcome(run(tmp_path / "b", "refused", reason="no_reference")) == ("refused", "no_reference", None)
    with pytest.raises(CheckFailed):
        w15_signs.outcome(tmp_path / "missing")


def test_judge_tells_noise_from_the_sign(tmp_path):
    knee_a = run(tmp_path / "a1", "done", level="knee")
    knee_b = run(tmp_path / "b1", "done", level="knee")
    refused = run(tmp_path / "x", "refused", reason="no_reference")
    assert w15_signs.judge(knee_a, refused, signed(tmp_path / "s0", "done", level="knee")) == "noisy"
    assert w15_signs.judge(knee_a, knee_b, signed(tmp_path / "s1", "done", level="knee")) == "match"
    assert w15_signs.judge(knee_a, knee_b, signed(tmp_path / "s2", "done", level="tire")) == "changed"
    assert w15_signs.judge(knee_a, knee_b, signed(tmp_path / "s3", "refused", reason="no_reference")) == "changed"


def test_a_failed_run_is_never_the_signs_effect(tmp_path):
    a = run(tmp_path / "a", "done", level="knee")
    b = run(tmp_path / "b", "done", level="knee")
    assert w15_signs.judge(a, b, signed(tmp_path / "s", "failed", reason="model_error")) == "failed"
    assert w15_signs.judge(a, run(tmp_path / "b2", "failed", reason="model_error"), signed(tmp_path / "s2", "done", level="knee")) == "failed"


def test_judge_refuses_runs_out_of_order(tmp_path):
    a = run(tmp_path / "a", "done", level="knee")
    b = run(tmp_path / "b", "done", level="knee")
    s = signed(tmp_path / "s", "done", level="knee")
    with pytest.raises(CheckFailed, match="plain"):
        w15_signs.judge(a, s, b)
    with pytest.raises(CheckFailed, match="signed"):
        w15_signs.judge(a, b, signed(tmp_path / "other", "done", level="knee", stem="q"))
    with pytest.raises(CheckFailed, match="plain"):
        w15_signs.judge(a, run(tmp_path / "q", "done", level="knee", photo="q-plain.jpg"), s)


def test_compare_counts_only_the_steady_photos(tmp_path, capsys):
    t = tmp_path

    def triple(n, a, b, s):
        return [run(t / f"{n}a", "done", level=a), run(t / f"{n}b", "done", level=b), signed(t / f"{n}s", *s)]

    runs = [
        *triple(1, "knee", "knee", ("done", None, "knee")),
        *triple(2, "knee", "waist", ("done", None, "knee")),
        *triple(3, "gutter", "gutter", ("done", None, "tire")),
        *triple(4, "knee", "knee", ("failed", "model_error", None)),
    ]
    code = w15_signs.main(["compare", *[str(p) for p in runs]])
    out = capsys.readouterr().out
    assert code == 0
    assert "1 of 2 counted photos match (indicative)" in out
    assert "1 noisy: photo 2" in out
    assert "1 failed: photo 4" in out
    assert w15_signs.main(["compare", *[str(p) for p in runs[:9]]]) == 2, "all four photos in one call"


def test_pairs_takes_the_11th_to_14th_credited_photos(tmp_path, data):
    from fake_aws import commons_folder
    from smoke_upload import credited, seeded_photo_order

    folder = commons_folder(data, [f"p{n:02}.jpg" for n in range(16)])
    made = w15_signs.pairs(folder)
    expected = credited(folder, seeded_photo_order(folder))[0][10:14]
    assert [plain.name for plain, _ in made] == [f"{p.stem}-plain.jpg" for p in expected]
    assert [s.name for _, s in made] == [f"{p.stem}-signed.jpg" for p in expected]
    assert all(plain.parent == data / "ms7" / "w15" for plain, _ in made)


def test_pairs_refuses_too_few_photos_another_folder_and_sealed(tmp_path, data):
    from fake_aws import commons_folder

    folder = commons_folder(data, [f"p{n:02}.jpg" for n in range(12)])
    with pytest.raises(CheckFailed, match="needs 4"):
        w15_signs.pairs(folder)
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(CheckFailed, match="C87"):
        w15_signs.pairs(other)
    with pytest.raises(CheckFailed, match="sealed"):
        w15_signs.pairs(tmp_path / "sealed" / "commons-ph-floods")


def test_make_without_the_folder_exits_2_and_prints_no_path(tmp_path, data, capsys):
    assert w15_signs.main(["make"]) == 2
    out = capsys.readouterr().out
    assert str(data) not in out
    assert w15_signs.main(["make", str(tmp_path)]) == 2, "make reads only C87's folder, so it takes no path"
