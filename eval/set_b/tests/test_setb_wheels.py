"""Tests for Set B's wheel choice (C212), and the masks folders synth lays out as
set_b_masks does."""

import hashlib

import numpy as np
import pytest
import synth
import wheels

SHAPE = (300, 500)  # (height, width), numpy's order
VEHICLE = (80, 40, 260, 380)  # rows 80 to 259 and columns 40 to 379
# Wheel ellipses, as (centre row, centre column), half-height and half-width, each with
# its half-open box (x0, y0, x1, y1).
LEFT = ((200, 100), 30, 25)
LEFT_BOX = (75, 170, 126, 231)
RIGHT = ((200, 300), 28, 24)
RIGHT_BOX = (276, 172, 325, 229)


def rect(y0: int, x0: int, y1: int, x1: int) -> np.ndarray:
    """A mask of SHAPE, true in rows y0 to y1 - 1 and columns x0 to x1 - 1."""
    mask = np.zeros(SHAPE, bool)
    mask[y0:y1, x0:x1] = True
    return mask


def ellipse(centre: tuple[int, int], half_h: float, half_w: float) -> np.ndarray:
    return synth.ellipse_mask(SHAPE, centre, half_h, half_w)


def loaded(root, vehicles, found_wheels, rims=()):
    """Write the masks with synth.masks_folder, then load each kind back."""
    folder = synth.masks_folder(
        root, "B01-1", synth.jpeg(1, SHAPE), vehicles, found_wheels, rims
    )
    return tuple(
        wheels.load_instances(folder / f"sam_{kind}_masks.npz")
        for kind in ("vehicle", "wheel", "wheel_rim")
    )


def test_two_largest_wheels_inside_the_vehicle(tmp_path):
    """The two largest wheels whose centres lie in the largest vehicle box come back
    left to right. The largest wheel of all lies in a smaller vehicle box, so it is
    left out, and so is the smallest wheel inside."""
    small_vehicle = rect(150, 400, 270, 490)
    outside = ellipse((200, 440), 34, 30)  # the largest, inside small_vehicle only
    middle = ellipse((200, 200), 22, 20)
    vehicles, found, _ = loaded(
        tmp_path,
        [small_vehicle, rect(*VEHICLE)],
        [ellipse(*RIGHT), outside, middle, ellipse(*LEFT)],
    )
    chosen = wheels.pick_wheels(vehicles, found, SHAPE)
    assert [wheel.box for wheel in chosen] == [LEFT_BOX, RIGHT_BOX]


@pytest.mark.parametrize(
    ("box", "kept"),
    [
        ((150, 0, 250, 80), False),  # touches the left edge
        ((150, 420, 250, 500), False),  # the right edge
        ((0, 200, 100, 280), False),  # the top edge
        ((200, 200, 300, 280), False),  # the bottom edge
        ((150, 200, 188, 238), False),  # 38 px tall and wide
        ((150, 200, 190, 240), True),  # 40 px
        ((100, 200, 185, 300), False),  # height over width 0.85
        ((100, 200, 190, 300), True),  # 0.9
        ((50, 200, 150, 250), True),  # 2.0
        ((50, 200, 155, 250), False),  # 2.1
    ],
)
def test_wheel_rules(tmp_path, box, kept):
    """A wheel is kept only when its mask touches no edge row or column, its longer
    side is at least 40 px, and its height over width is 0.9 to 2.0, both inclusive.
    The vehicle fills the frame, so every centre lies inside it."""
    vehicles, found, _ = loaded(tmp_path, [rect(0, 0, *SHAPE)], [rect(*box)])
    chosen = wheels.pick_wheels(vehicles, found, SHAPE)
    if kept:
        assert [wheel.box for wheel in chosen] == [(box[1], box[0], box[3], box[2])]
    else:
        assert chosen == "no_wheel"


def test_no_vehicle_and_no_wheel_causes(tmp_path):
    """No vehicle gives no_vehicle; no wheel, or none that meets the rules, no_wheel."""
    vehicles, found, _ = loaded(tmp_path / "a", [], [ellipse(*LEFT)])
    assert vehicles == []
    assert wheels.pick_wheels(vehicles, found, SHAPE) == "no_vehicle"
    vehicles, found, _ = loaded(tmp_path / "b", [rect(*VEHICLE)], [])
    assert wheels.pick_wheels(vehicles, found, SHAPE) == "no_wheel"
    outside = ellipse((200, 440), 34, 30)
    vehicles, found, _ = loaded(tmp_path / "c", [rect(*VEHICLE)], [outside])
    assert wheels.pick_wheels(vehicles, found, SHAPE) == "no_wheel"


def test_ties_keep_input_order(tmp_path):
    """Of two vehicle boxes with one area, the first counts as the largest; of wheels
    with one mask area, the first two in the input are used."""
    left_vehicle, right_vehicle = rect(80, 40, 260, 240), rect(80, 260, 260, 460)
    a, b, c = (ellipse((200, x), 20, 18) for x in (100, 140, 180))
    other = ellipse((200, 400), 20, 18)  # inside right_vehicle
    vehicles, found, _ = loaded(
        tmp_path / "a", [left_vehicle, right_vehicle], [c, b, other, a]
    )
    chosen = wheels.pick_wheels(vehicles, found, SHAPE)
    assert [wheel.box[0] for wheel in chosen] == [122, 162]  # b and c, left to right
    vehicles, found, _ = loaded(
        tmp_path / "b", [right_vehicle, left_vehicle], [c, b, other, a]
    )
    chosen = wheels.pick_wheels(vehicles, found, SHAPE)
    assert [wheel.box[0] for wheel in chosen] == [382]


def test_link_rim_by_overlap(tmp_path):
    """The rim mask that overlaps the wheel mask most is linked, and None when none
    overlaps."""
    far = ellipse((200, 300), 15, 12)  # no overlap
    corner = rect(190, 60, 210, 80)  # a few pixels of the wheel's left side
    inside = ellipse((200, 100), 18, 15)  # wholly inside the wheel
    _, (wheel,), rims = loaded(
        tmp_path, [rect(*VEHICLE)], [ellipse(*LEFT)], [far, corner, inside]
    )
    assert wheels.link_rim(wheel, rims).box == (85, 182, 116, 219)
    assert wheels.link_rim(wheel, rims[:1]) is None
    assert wheels.link_rim(wheel, []) is None


def test_load_instances_round_trip(tmp_path):
    """Each instance comes back with its mask, a half-open box from the mask's own
    extent, and its score, NaN loading as None. The npz holds set_b_masks' four arrays,
    and an empty list still has the image's shape."""
    vehicle, left, right = rect(*VEHICLE), ellipse(*LEFT), ellipse(*RIGHT)
    vehicles, found, rims = loaded(tmp_path, [vehicle], [left, right])
    assert [v.box for v in vehicles] == [(40, 80, 380, 260)]
    assert [w.box for w in found] == [LEFT_BOX, RIGHT_BOX]
    assert np.array_equal(vehicles[0].mask, vehicle)
    assert np.array_equal(found[0].mask, left) and np.array_equal(found[1].mask, right)
    assert [w.score for w in [*vehicles, *found]] == [None, None, None]
    assert rims == []
    with np.load(tmp_path / "B01-1" / "sam_wheel_masks.npz") as data:
        assert sorted(data.files) == ["boxes", "ids", "masks", "scores"]
        assert data["ids"].tolist() == [0, 1]
        assert data["boxes"].tolist() == [list(LEFT_BOX), list(RIGHT_BOX)]
        assert np.isnan(data["scores"]).all()
        assert data["masks"].dtype == bool and data["masks"].shape == (2, *SHAPE)
    with np.load(tmp_path / "B01-1" / "sam_wheel_rim_masks.npz") as data:
        assert data["masks"].shape == (0, *SHAPE) and data["boxes"].shape == (0, 4)
    scored = tmp_path / "scored.npz"
    np.savez_compressed(
        scored,
        ids=np.array([3, 4]),
        boxes=np.array([LEFT_BOX, RIGHT_BOX], float),
        scores=np.array([0.87, np.nan]),
        masks=np.array([left, right]),
    )
    assert [w.score for w in wheels.load_instances(scored)] == [0.87, None]


def test_load_instances_refuses_pickles(tmp_path):
    """np.load keeps allow_pickle=False, so an object array is refused, never run."""
    pickled = tmp_path / "pickled.npz"
    np.savez_compressed(
        pickled,
        ids=np.array([0]),
        boxes=np.zeros((1, 4)),
        scores=np.array([None], object),
        masks=np.array([ellipse(*LEFT)]),
    )
    with pytest.raises(ValueError):
        wheels.load_instances(pickled)


def test_empty_masks_are_skipped(tmp_path):
    """An empty mask has no extent, so it gives no instance."""
    _, found, _ = loaded(
        tmp_path, [rect(*VEHICLE)], [np.zeros(SHAPE, bool), ellipse(*LEFT)]
    )
    assert [w.box for w in found] == [LEFT_BOX]
    with np.load(tmp_path / "B01-1" / "sam_wheel_masks.npz") as data:
        assert data["masks"].shape == (2, *SHAPE)


def test_masks_folder_merges_files_txt(tmp_path):
    """synth.masks_folder writes the four files the generator reads, and merges them,
    hashed, into the root's files.txt, sorted by path, with \\n endings and no BOM. A
    second stem keeps the first's entries, and a repeated path takes its new hash."""
    root = tmp_path / "masks"
    names = (
        "blurred.jpg",
        "sam_vehicle_masks.npz",
        "sam_wheel_masks.npz",
        "sam_wheel_rim_masks.npz",
    )

    def write(stem: str, seed: int):
        photo = synth.jpeg(seed, SHAPE)
        folder = synth.masks_folder(
            root, stem, photo, [rect(*VEHICLE)], [ellipse(*LEFT)], [ellipse(*LEFT)]
        )
        assert folder == root / stem
        assert (folder / "blurred.jpg").read_bytes() == photo
        assert not (folder / "meta.json").exists()
        assert not (folder / "sam_wheel.txt").exists()

    def listing() -> dict[str, str]:
        data = (root / "files.txt").read_bytes()
        assert not data.startswith(b"\xef\xbb\xbf") and b"\r" not in data
        assert data.endswith(b"\n")
        lines = data.decode("utf-8").splitlines()
        paths = [line.split("  ", 1)[1] for line in lines]
        assert paths == sorted(paths)
        entries = {
            path: line.split("  ", 1)[0]
            for line, path in zip(lines, paths, strict=True)
        }
        for path, digest in entries.items():
            assert hashlib.sha256((root / path).read_bytes()).hexdigest() == digest
        return entries

    write("B01-1", 1)
    first = listing()
    assert list(first) == [f"B01-1/{name}" for name in names]
    write("B03-1", 3)
    second = listing()
    assert list(second) == [
        f"{stem}/{name}" for stem in ("B01-1", "B03-1") for name in names
    ]
    assert {path: second[path] for path in first} == first
    write("B01-1", 5)
    third = listing()
    assert list(third) == list(second)
    assert third["B01-1/blurred.jpg"] != first["B01-1/blurred.jpg"]
    assert third["B03-1/blurred.jpg"] == second["B03-1/blurred.jpg"]
