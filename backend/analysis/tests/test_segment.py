"""Tests for step 2: SAM on every phrase at once, and each wheel's vehicle (C55)."""

import threading

import numpy as np
import pytest
from fakes import FakeClient, around, instance, meta_error, noise_jpeg, sam_results

from lusot_analysis.face_blur import BlurredImage, blur_for_meta
from lusot_analysis.meta_client import SAM_PHRASES, MetaApiError, SamInstance
from lusot_analysis.pipeline.segment import box_xyxy, link_wheels, segment_all

# Vehicles A, B and C. A and B overlap from x 150 to 200.
VEHICLES = [(0, 0, 200, 100), (150, 0, 400, 100), (0, 200, 100, 300)]


@pytest.fixture(scope="module")
def image() -> BlurredImage:
    return blur_for_meta(noise_jpeg())


def test_box_xyxy_reads_the_client_convention():
    # MS1's client keeps a SAM box half-open, as (x0, y0, x1, y1) in pixels of the
    # image sent (R61). SAM's documented record x1=211;y1=228;x2=270;y2=254 has
    # inclusive x2 and y2, so the client stores (211, 228, 271, 255)
    # (test_meta_client.py, test_segment_box_is_half_open_in_sent_pixels).
    mask = np.zeros((334, 320), bool)
    mask[228:255, 211:271] = True
    documented = SamInstance(0, (211.0, 228.0, 271.0, 255.0), mask, None)
    x0, y0, x1, y1 = box_xyxy(documented)
    assert (x0, y0, x1, y1) == (211.0, 228.0, 271.0, 255.0)
    assert (x1 - x0, y1 - y0) == (60, 27)  # the width and height, with no + 1
    # mask[y0:y1, x0:x1] holds the whole match.
    assert mask[int(y0) : int(y1), int(x0) : int(x1)].sum() == mask.sum()


def test_instance_builder_keeps_the_client_convention():
    # The fakes keep a box as the client does, so box_xyxy reads it back unchanged,
    # and the mask fills the same half-open box.
    built = instance(3, (211, 228, 271, 255), size=(320, 334))
    assert box_xyxy(built) == (211.0, 228.0, 271.0, 255.0)
    assert built.mask.shape == (334, 320)
    assert built.mask[228:255, 211:271].all()
    assert built.mask.sum() == 60 * 27


def test_segment_all_runs_every_phrase_at_once(image):
    # Each call waits until all 7 are in flight. Calls made one after another would
    # break the barrier after 5 s, and its error would fail the test.
    barrier = threading.Barrier(7, timeout=5)
    sam = sam_results({})
    client = FakeClient(sam, on_segment=lambda phrase: barrier.wait())
    results = segment_all(client, image, SAM_PHRASES)
    assert results.keys() == set(SAM_PHRASES)
    assert all(results[phrase] is sam[phrase] for phrase in SAM_PHRASES)
    assert sorted(phrase for _, phrase, _ in client.calls) == sorted(SAM_PHRASES)
    assert {(method, kind) for method, _, kind in client.calls} == {
        ("segment", BlurredImage)
    }


def test_segment_all_propagates_a_meta_error(image):
    error = meta_error(503)

    def on_segment(phrase):
        if phrase == "wheel":
            raise error

    client = FakeClient(sam_results({}), on_segment=on_segment)
    with pytest.raises(MetaApiError) as exc:
        segment_all(client, image, SAM_PHRASES)
    assert exc.value is error  # unwrapped, so its status reaches the error mapping
    assert exc.value.status == 503


@pytest.mark.parametrize(
    ("errors", "raised_by"),
    [
        # R107: a rejected key or account goes first, from any phrase (C73).
        pytest.param(
            {"floodwater": meta_error(500), "wheel": meta_error(401)},
            "wheel",
            id="500-then-401",
        ),
        pytest.param(
            {
                "floodwater": MetaApiError("connection failed or timed out"),
                "wheel": meta_error(403),
            },
            "wheel",
            id="timeout-then-403",
        ),
        pytest.param(
            {"floodwater": KeyError("boom"), "wheel": meta_error(402)},
            "wheel",
            id="not-meta-then-402",
        ),
        pytest.param(
            {"floodwater": meta_error(403), "wheel": meta_error(401)},
            "floodwater",
            id="two-rejections",
        ),
        # Otherwise the first error in phrase order, as before.
        pytest.param(
            {"floodwater": meta_error(500), "wheel": meta_error(503)},
            "floodwater",
            id="two-other-errors",
        ),
    ],
)
def test_segment_all_raises_a_rejected_key_first(image, errors, raised_by):
    def on_segment(phrase):
        if phrase in errors:
            raise errors[phrase]

    client = FakeClient(sam_results({}), on_segment=on_segment)
    with pytest.raises(MetaApiError) as exc:
        segment_all(client, image, SAM_PHRASES)
    assert exc.value is errors[raised_by]


def test_link_wheels_by_centre():
    vehicles = [instance(i, box) for i, box in enumerate(VEHICLES)]
    centres = [
        (50, 50),  # inside A
        (300, 50),  # inside B
        (175, 50),  # inside both A and B
        (500, 50),  # inside neither
        (100, 250),  # on C's edge, which counts
    ]
    wheels = [instance(i, around(*centre)) for i, centre in enumerate(centres)]
    assert link_wheels(vehicles, wheels) == [0, 1, None, None, 2]


@pytest.mark.parametrize(
    ("centre", "link"),
    [
        ((100, 150), 0),  # on the left edge
        ((300, 150), 0),  # on the right edge
        ((200, 100), 0),  # on the top edge
        ((200, 200), 0),  # on the bottom edge
        ((99, 150), None),  # just outside each edge
        ((301, 150), None),
        ((200, 99), None),
        ((200, 201), None),
    ],
)
def test_link_wheels_counts_every_edge(centre, link):
    vehicle = instance(0, (100, 100, 300, 200))
    assert link_wheels([vehicle], [instance(1, around(*centre))]) == [link]
