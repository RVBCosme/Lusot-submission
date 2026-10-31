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


def run(folder: Path, status: str, reason: str | None = None, level: str | None = None) -> Path:
    folder.mkdir(parents=True)
    outcome = {"status": status, "reason": reason, "no_flood_seen": False, "level": level}
    (folder / "run.json").write_text(json.dumps({"outcome": outcome}), encoding="utf-8")
    return folder


def test_outcome_reads_a_saved_run(tmp_path):
    assert w15_signs.outcome(run(tmp_path / "a", "done", level="knee")) == ("done", None, "knee")
    assert w15_signs.outcome(run(tmp_path / "b", "refused", reason="no_reference")) == ("refused", "no_reference", None)
    with pytest.raises(CheckFailed):
        w15_signs.outcome(tmp_path / "missing")


def test_judge_tells_noise_from_the_sign(tmp_path):
    knee_a = run(tmp_path / "a1", "done", level="knee")
    knee_b = run(tmp_path / "b1", "done", level="knee")
    tire = run(tmp_path / "s1", "done", level="tire")
    knee_s = run(tmp_path / "s2", "done", level="knee")
    refused = run(tmp_path / "x", "refused", reason="no_reference")
    assert w15_signs.judge(knee_a, refused, knee_s) == "noisy"
    assert w15_signs.judge(knee_a, knee_b, knee_s) == "match"
    assert w15_signs.judge(knee_a, knee_b, tire) == "changed"
    assert w15_signs.judge(knee_a, knee_b, refused) == "changed"


def test_compare_counts_only_the_steady_photos(tmp_path, capsys):
    t = tmp_path
    triples = [
        (run(t / "1a", "done", level="knee"), run(t / "1b", "done", level="knee"), run(t / "1s", "done", level="knee")),
        (run(t / "2a", "done", level="knee"), run(t / "2b", "done", level="waist"), run(t / "2s", "done", level="knee")),
        (run(t / "3a", "done", level="gutter"), run(t / "3b", "done", level="gutter"), run(t / "3s", "done", level="tire")),
    ]
    code = w15_signs.main(["compare", *[str(p) for triple in triples for p in triple]])
    out = capsys.readouterr().out
    assert code == 0
    assert "1 of 2 counted photos match" in out
    assert "1 noisy" in out
    assert "indicative" in out
    assert w15_signs.main(["compare", str(t / "1a"), str(t / "1b")]) == 2, "runs come in threes"
