"""Laptop Meta spend, added to MS4's spend counter (C527, R126).

The counter's stop, /lusot/spend/stop-usd, guards the $150 Meta credit only if every
dollar spent reaches the counter. So each laptop tool that calls Meta itself counts
its calls and records their cost: probes/run_pipeline.py live, dev_eval.py run,
set_b.py segment and rims, set_b_masks.py, run_probe.py and run_sealed.py. The tools
that send photos to the cloud never do (smoke_upload.py, the sample and demo seeds,
eval_runs): the Lambda counts that spend itself. A free path (a replay, an export, an
overlay) makes no Meta call, so it reads no counter and needs no AWS.

- check_before_paying(), before the first paid call and before any Meta client is
  built: the counter, read with the lusot profile, must be seeded, readable and below
  its stop, or the tool exits 2 with one fixed line.
- CountedClient wraps the Meta client and tallies what its calls may cost, at
  spend.PRICES, as the analysis handler counts a run (MS4).
- SpendCounter.record_after(usd, source), after the paid work: one atomic ADD. A
  failed write prints one spend_error line with the amount and the source, and exits
  3 (R110's run failure) through SpendNotRecorded. The run's outputs stay saved, and
  the tracker adds the amount by hand with spend.py's `add`.

spend.py stays MS4's, unchanged. The lusot profile's `aws login` credentials need
botocore's CRT, which uv.lock leaves out, so a paid run adds
`--with "botocore[crt]==1.43.120"` to its `uv run`, as spend.py's own CLI does.
Every line printed masks runs of 12 digits.
"""

from __future__ import annotations

import io
import re
import threading
import wave
from decimal import Decimal
from typing import NoReturn

from botocore.exceptions import BotoCoreError, ClientError, MissingDependencyException

from lusot_analysis.meta_client import MetaApiError
from lusot_analysis.spend import (
    SPARK_TOKENS_IF_UNREPORTED,
    SPEND_CONFIG,
    SPEND_STOP_PARAM,
    SpendUnseeded,
    aws_error,
    cost_of,
    deployed_limits_table,
    operator_session,
    parse_usd,
    record_spend,
    rounded_up,
    spend_total,
)

REFUSED_EXIT = 2  # a refusal: nothing was paid for
SPEND_ERROR_EXIT = 3  # R110's run failure: paid for, but not on the counter
UNSEEDED = "the spend counter isn't seeded, so this run can't be counted"
UNREADABLE = (
    "the spend counter can't be read; sign in with `aws login --profile lusot` first"
)
NEEDS_CRT = (
    "the lusot profile's `aws login` credentials need botocore's CRT: run with"
    ' uv run --with "botocore[crt]==1.43.120"'
)
BAD_STOP = "the spend stop isn't a number, so this run can't be held to it"
_ACCOUNT_ID = re.compile("[0-9]{12}")


class SpendNotRecorded(SystemExit):
    """A paid run's cost that couldn't be added to the counter (R126): exit 3.

    record_after prints the spend_error line before raising it. It is a SystemExit,
    so every tool exits 3 on it however it handles its other failures.
    """

    def __init__(self) -> None:
        super().__init__(SPEND_ERROR_EXIT)


class SpendCounter:
    """MS4's counter, read and found below its stop by check_before_paying."""

    def __init__(self, ddb, table: str) -> None:
        self._ddb = ddb
        self._table = table

    def record_after(self, usd: Decimal, source: str) -> None:
        """Add `usd` to the counter, after the paid work, in one atomic ADD.

        Nothing billed records nothing. `source` is a tool's name, such as
        run_pipeline: never a path or a photo. A write that fails, after SPEND_CONFIG's
        retries, prints one spend_error line with the amount as the counter would add
        it, and raises SpendNotRecorded.
        """
        if usd <= 0:
            return
        try:
            record_spend(usd, source, ddb=self._ddb, table=self._table)
        # Any failure, Ctrl+C mid-write too: the amount is still owed (R126).
        except BaseException as exc:  # noqa: BLE001
            amount = rounded_up(usd)
            _say(
                f"spend_error: ${amount} from {source} isn't on the spend counter"
                f" ({aws_error(exc)}); add it by hand with spend.py add --usd {amount}"
                " --source manual-<who>"
            )
            raise SpendNotRecorded from None


# The deployed functions' model-calls switch (C60). C533's credit guard sets it on when the
# Meta credits lapse, so a laptop tool must stop with them, or it bills the card.
MODEL_CALLS_SWITCH = "/lusot/stop/model-calls"


def check_before_paying(*, session=None) -> SpendCounter:
    """MS4's counter, read before the first paid call and any Meta client (C527).

    `session` is the lusot profile's (spend.operator_session), unless a test gives
    one. The run goes on only when the counter is seeded, readable and below the stop
    in SPEND_STOP_PARAM, and MODEL_CALLS_SWITCH reads exactly "off", as the deployed
    handler requires (C60, C533). Otherwise it exits 2 with one fixed line: the switch
    not off; unseeded; unread,
    as with no credentials or an expired login (the AWS error's code follows, never
    its message); the CRT missing; a stop that isn't a number; or a total at or over
    the stop.
    """
    try:
        session = operator_session() if session is None else session
        ddb = session.client("dynamodb", config=SPEND_CONFIG)
        table = deployed_limits_table(session)
        total = spend_total(ddb=ddb, table=table)
        ssm = session.client("ssm", config=SPEND_CONFIG)
        value = ssm.get_parameter(Name=SPEND_STOP_PARAM)["Parameter"]["Value"]
        switch = ssm.get_parameter(Name=MODEL_CALLS_SWITCH)["Parameter"]["Value"]
    except SpendUnseeded:
        _refuse(UNSEEDED)
    except MissingDependencyException:  # a BotoCoreError, so before the next clause
        _refuse(NEEDS_CRT)
    except (BotoCoreError, ClientError) as exc:
        _refuse(f"{UNREADABLE} ({aws_error(exc)})")
    if switch != "off":
        _refuse("the model-calls switch isn't off, so no paid call runs (C533)")
    stop = parse_usd(value)
    if stop is None:
        _refuse(BAD_STOP)
    if total >= stop:
        _refuse(f"the spend counter is at its stop: ${total} of ${stop}")
    return SpendCounter(ddb, table)


class CountedClient:
    """The Meta client, with a tally of what its calls may cost, at spend.PRICES.

    It counts as the analysis handler's _CountedClient counts a run (MS4): each SAM
    call that returns is one image, and each Muse Spark answer adds its tokens, or
    SPARK_TOKENS_IF_UNREPORTED for a count Meta didn't report. A transcript adds its
    clip's whole seconds, rounded up, read from the WAV before it is sent. A call that
    raised is charged the same, unless Meta answered it with an HTTP error, which
    isn't billed: a timeout, an unfinished or unreadable answer, a refusal or Ctrl+C
    may have been. count_input_tokens is passed on uncounted, as PRICES has no price
    for it (run_probe's note). SAM's phrases run in parallel threads, so the tally
    takes a lock.
    """

    def __init__(self, client) -> None:
        self._client = client
        self._lock = threading.Lock()
        self._sam_images = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._audio_seconds = 0

    def segment(self, image, phrase: str, **kwargs):
        try:
            result = self._client.segment(image, phrase, **kwargs)
        except BaseException as exc:
            if _maybe_billed(exc):
                self._add(images=1)
            raise
        self._add(images=1)
        return result

    def judge(self, image, **kwargs):
        try:
            answer = self._client.judge(image, **kwargs)
        except BaseException as exc:
            if _maybe_billed(exc):
                self._add(tokens=SPARK_TOKENS_IF_UNREPORTED)
            raise
        reported = (answer.input_tokens, answer.output_tokens)
        tokens = tuple(
            fallback if count is None else count
            for count, fallback in zip(
                reported, SPARK_TOKENS_IF_UNREPORTED, strict=True
            )
        )
        self._add(tokens=tokens)
        return answer

    def transcribe(self, wav: bytes, **kwargs):
        seconds = _billed_seconds(wav)  # a clip it can't read is never sent
        try:
            result = self._client.transcribe(wav, **kwargs)
        except BaseException as exc:
            if _maybe_billed(exc):
                self._add(seconds=seconds)
            raise
        self._add(seconds=seconds)
        return result

    def count_input_tokens(self, image, **kwargs) -> int:
        return self._client.count_input_tokens(image, **kwargs)

    def take(self) -> Decimal:
        """What the calls since the last take cost, in USD. The tally starts again, so
        an amount is recorded, or reported as a spend_error, once."""
        with self._lock:
            cost = cost_of(
                sam_images=self._sam_images,
                spark_input_tokens=self._input_tokens,
                spark_output_tokens=self._output_tokens,
                audio_seconds=self._audio_seconds,
            )
            self._sam_images = self._input_tokens = self._output_tokens = 0
            self._audio_seconds = 0
        return cost

    def _add(
        self,
        *,
        images: int = 0,
        tokens: tuple[int, int] = (0, 0),
        seconds: int = 0,
    ) -> None:
        with self._lock:
            self._sam_images += images
            self._input_tokens += tokens[0]
            self._output_tokens += tokens[1]
            self._audio_seconds += seconds


def _maybe_billed(exc: BaseException) -> bool:
    """Whether a Meta call that raised `exc` may still have been billed: all but
    Meta's own HTTP error answer, a MetaApiError with a status."""
    return not (isinstance(exc, MetaApiError) and exc.status is not None)


def _billed_seconds(wav: bytes) -> int:
    """A WAV clip's length in whole seconds, rounded up, as transcription is billed."""
    with wave.open(io.BytesIO(wav)) as clip:
        frames, rate = clip.getnframes(), clip.getframerate()
    return -(-frames // rate)


def _say(line: str) -> None:
    print(_ACCOUNT_ID.sub("<account>", line), flush=True)


def _refuse(message: str) -> NoReturn:
    _say(f"refused: {message}")
    raise SystemExit(REFUSED_EXIT)
