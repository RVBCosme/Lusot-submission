"""Tests for the numbered boxes Muse Spark sees (plan §7 step 4)."""

import math
from pathlib import Path

import cv2
import numpy as np

from lusot_analysis.annotate import (
    NumberedBox,
    check_ids,
    draw_numbered_boxes,
    number_boxes,
)
from lusot_analysis.face_blur import BlurredImage, blur_for_meta, detect_faces
from lusot_analysis.meta_client import SamInstance, SamResult

PORTRAIT = Path(__file__).parent / "fixtures" / "faces" / "portrait.jpg"
# derive re-encodes the JPEG at quality 90. On texture() that alone moves pixels by
# up to 16 levels, and by about 1.5 on average (R14).
REENCODE_TOLERANCE = 20


def sam(phrase: str, *boxes: tuple[float, float, float, float]) -> SamResult:
    """SAM's result for `phrase`: one instance per box, in the given order."""
    instances = [
        SamInstance(i, box, np.zeros((1, 1), bool), 0.9) for i, box in enumerate(boxes)
    ]
    return SamResult(phrase, instances, 0.5, "")


def jpeg(bgr: np.ndarray) -> bytes:
    return cv2.imencode(".jpg", bgr)[1].tobytes()


def texture(width: int, height: int) -> np.ndarray:
    """Smooth colour blobs over the full range: photo-like detail, and no face."""
    noise = np.random.default_rng(0).integers(0, 256, (height, width, 3), np.uint8)
    return cv2.normalize(
        cv2.GaussianBlur(noise, (0, 0), 2), None, 0, 255, cv2.NORM_MINMAX
    )


def test_number_boxes_is_one_sequence():
    # The keys come in another order than the numbering, and each kind's boxes out of
    # position order: every kind keeps SAM's order (R66), and other phrases get no id.
    results = {
        "person": sam("person", (500, 40, 560, 200)),
        "wheel": sam(
            "wheel", (300, 150, 340, 190), (40, 150, 80, 190), (200, 150, 240, 190)
        ),
        "floodwater": sam("floodwater", (0, 180, 640, 480)),
        "vehicle": sam("vehicle", (250, 60, 400, 200), (20, 60, 260, 200)),
        "face": sam("face", (510, 50, 530, 70)),
    }
    assert number_boxes(results) == [
        NumberedBox(1, "vehicle", (250, 60, 400, 200)),
        NumberedBox(2, "vehicle", (20, 60, 260, 200)),
        NumberedBox(3, "wheel", (300, 150, 340, 190)),
        NumberedBox(4, "wheel", (40, 150, 80, 190)),
        NumberedBox(5, "wheel", (200, 150, 240, 190)),
        NumberedBox(6, "person", (500, 40, 560, 200)),
    ]


def test_number_boxes_rounds_outward():
    # Whole pixels, still half-open and still holding the whole match (R74): the start
    # is floored and the end ceiled. A phrase missing from the results has no boxes.
    boxes = number_boxes({"wheel": sam("wheel", (10.2, 20.7, 30.0, 40.1))})
    assert boxes == [NumberedBox(1, "wheel", (10, 20, 30, 41))]
    assert all(type(v) is int for v in boxes[0].box)


def test_draw_numbered_boxes_keeps_blur_provenance():
    base = blur_for_meta(jpeg(texture(640, 480)))
    assert base.faces == 0  # so derive has no face to blur again
    boxes = [
        NumberedBox(1, "vehicle", (64, 96, 448, 400)),
        NumberedBox(2, "wheel", (96, 288, 208, 400)),
        NumberedBox(3, "person", (480, 48, 608, 448)),
    ]
    out = draw_numbered_boxes(base, boxes)
    assert type(out) is BlurredImage
    assert (out.faces, out.blur_version) == (base.faces, base.blur_version)
    assert (out.width, out.height) == (base.width, base.height)

    # Where the outlines and labels are: the same boxes drawn on black and on white.
    drawn = np.zeros((480, 640), bool)
    for value in (0, 255):
        flat = blur_for_meta(jpeg(np.full((480, 640, 3), value, np.uint8)))
        ink = draw_numbered_boxes(flat, boxes).bgr().astype(int)
        drawn |= (np.abs(ink - value) > 40).any(axis=2)
    # A JPEG block is 16 x 16 px, so a drawn line's ringing reaches up to 16 px away.
    away = cv2.dilate(drawn.astype(np.uint8), np.ones((35, 35), np.uint8)) == 0

    diff = np.abs(out.bgr().astype(int) - base.bgr().astype(int)).max(axis=2)
    assert diff[away].max() <= REENCODE_TOLERANCE
    # Nothing is filled: most of each box lies away from the drawing, and there it is
    # unchanged on average. Even a faint fill would shift it by tens of levels.
    for box in boxes:
        x0, y0, x1, y1 = box.box
        inside = away[y0:y1, x0:x1]
        assert inside.mean() > 0.3
        assert diff[y0:y1, x0:x1][inside].mean() < 3


def label_strokes(
    img: BlurredImage,
    box: tuple[int, int, int, int],
    kind: str = "person",
    after: tuple[NumberedBox, ...] = (),
) -> np.ndarray:
    """Where `box`'s label reading 1 and reading 8 differ: the digits' strokes.

    The box is drawn first and the boxes in `after` next. Every digit is drawn the
    same width, so the swap moves no label.
    """
    one, eight = (
        draw_numbered_boxes(img, [NumberedBox(i, kind, box), *after]).bgr().astype(int)
        for i in (1, 8)
    )
    return np.abs(one - eight).max(axis=2) > 100


def test_label_beside_a_face_stays_legible():
    # derive blurs every face it finds once more (R18), and YuNet still finds the
    # blurred portrait's face, so a label drawn on the head would come out smeared.
    base = blur_for_meta(PORTRAIT.read_bytes())
    faces = detect_faces(base.bgr())
    face = max(faces, key=lambda f: f.score)
    # A person box drawn around the face: its top corners lie in the face's blur area.
    box = (face.x, face.y, face.x + face.w, base.height)
    strokes = label_strokes(base, box)
    # The digits are as crisp as the same label's on a plain grey photo of that size.
    grey = blur_for_meta(jpeg(np.full((base.height, base.width, 3), 128, np.uint8)))
    crisp = label_strokes(grey, box).sum()
    assert crisp > 0
    assert strokes.sum() >= 0.8 * crisp
    # And none of them is in a face's blur area: its box grown by 25% on every side.
    ys, xs = np.nonzero(strokes)
    for f in faces:
        dx, dy = math.ceil(f.w * 0.25), math.ceil(f.h * 0.25)
        in_x = (xs >= f.x - dx) & (xs < f.x + f.w + dx)
        in_y = (ys >= f.y - dy) & (ys < f.y + f.h + dy)
        assert not (in_x & in_y).any()


def test_a_label_never_covers_an_earlier_one():
    # Found by the MS1 probe (car-1510): two boxes whose top-left corners sat 7 px apart
    # at the top of the photo got their labels at almost the same place, and the later
    # label hid the earlier id from Muse Spark.
    grey = blur_for_meta(jpeg(np.full((448, 404, 3), 128, np.uint8)))
    first = (38, 11, 97, 38)
    later = NumberedBox(4, "vehicle", (45, 7, 404, 388))
    alone = label_strokes(grey, first, "vehicle").sum()
    assert alone > 0
    assert label_strokes(grey, first, "vehicle", (later,)).sum() >= 0.8 * alone


BOXES = [
    NumberedBox(1, "vehicle", (0, 0, 100, 60)),
    NumberedBox(2, "wheel", (10, 40, 30, 60)),
    NumberedBox(3, "wheel", (70, 40, 90, 60)),
    NumberedBox(4, "person", (120, 0, 140, 60)),
]


def answer(vehicles=(), wheels=(), people=()) -> dict:
    """An answer naming the given ids; check_ids reads only the ids."""
    return {
        "photo_usable": "yes",
        "standing_water": "yes",
        "vehicles": [{"id": i} for i in vehicles],
        "wheels": [{"id": i} for i in wheels],
        "people": [{"id": i} for i in people],
        "reason": "",
    }


def test_check_ids_passes_a_clean_answer():
    assert check_ids(answer(vehicles=[1], wheels=[2, 3], people=[4]), BOXES) == []
    assert check_ids(answer(), BOXES) == []  # leaving a box out isn't a problem


def test_check_ids_flags_unknown_and_wrong_kind():
    problems = check_ids(answer(vehicles=[1, 3], wheels=[2], people=[99]), BOXES)
    assert problems == ["wheel id 3 in vehicles", "unknown id 99 in people"]


def test_check_ids_flags_an_id_answered_twice():
    # Twice in one list, and once each in two lists (R73).
    assert check_ids(answer(wheels=[2, 2]), BOXES) == ["id 2 answered 2 times"]
    assert check_ids(answer(wheels=[3], people=[3]), BOXES) == [
        "wheel id 3 in people",
        "id 3 answered 2 times",
    ]
