"""Step 2: SAM looks for every phrase at once, and each wheel joins its vehicle.

Spec §3.2 step 2. Rims are linked in MS3b, because no 3a step reads one (C55).
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor

from lusot_analysis.face_blur import BlurredImage
from lusot_analysis.meta_client import MetaApiError, SamInstance, SamResult
from lusot_analysis.pipeline.types import KEY_REJECTED_STATUSES, ModelClient


def box_xyxy(inst: SamInstance) -> tuple[float, float, float, float]:
    """The instance's box as (x0, y0, x1, y1), in pixels of the image sent to SAM.

    MS1's client already keeps this order, half-open: x1 and y1 are one past the last
    column and row, so the width is x1 - x0, with no + 1 (R61). The pipeline's steps
    read a box only through here.
    """
    x0, y0, x1, y1 = inst.box
    return x0, y0, x1, y1


def segment_all(
    client: ModelClient,
    image: BlurredImage,
    phrases: Sequence[str],
    *,
    deadline: float | None = None,
) -> dict[str, SamResult]:
    """Ask SAM for every phrase at once, one thread each, keyed by phrase.

    The threads share the client and its connections (R61). Each call runs under
    `deadline`, the run's (C84). If calls raise, one error propagates, unwrapped,
    once every call has ended, so a MetaApiError keeps its status:
    - the first MetaApiError in phrase order whose status is 401, 402 or 403, ahead
      of any other failure, so another phrase's error can't hide a rejected key or
      account (C73, R107)
    - otherwise the first error in phrase order
    """
    with ThreadPoolExecutor(max_workers=len(phrases)) as pool:
        futures = {
            phrase: pool.submit(client.segment, image, phrase, deadline=deadline)
            for phrase in phrases
        }
    for future in futures.values():  # a rejected key or account first (R107)
        error = future.exception()
        if isinstance(error, MetaApiError) and error.status in KEY_REJECTED_STATUSES:
            raise error
    return {phrase: future.result() for phrase, future in futures.items()}


def link_wheels(
    vehicles: Sequence[SamInstance], wheels: Sequence[SamInstance]
) -> list[int | None]:
    """For each wheel, the index of the one vehicle whose box holds its box's centre.

    A box holds a point on its edge. A wheel whose centre no vehicle box holds, or
    more than one does, links to None: picking one of two cars would be a guess (C55).
    """
    boxes = [box_xyxy(vehicle) for vehicle in vehicles]
    links: list[int | None] = []
    for wheel in wheels:
        x0, y0, x1, y1 = box_xyxy(wheel)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        holders = [
            index
            for index, (vx0, vy0, vx1, vy1) in enumerate(boxes)
            if vx0 <= cx <= vx1 and vy0 <= cy <= vy1
        ]
        links.append(holders[0] if len(holders) == 1 else None)
    return links
