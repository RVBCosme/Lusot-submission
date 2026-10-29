"""Kappa by its formula, checked against scikit-learn (rules §7; C401, C405)."""

from __future__ import annotations

import math
import random
from fractions import Fraction

import pytest
from scoring.metrics import quadratic_kappa, score_set_a
from sklearn.exceptions import UndefinedMetricWarning
from sklearn.metrics import cohen_kappa_score
from test_set_a import HAND_SET, load_set_a

LABELS = list(range(9))


def sklearn_kappa(pairs: list[tuple[int, int]]) -> float:
    truth = [i for i, _ in pairs]
    readings = [j for _, j in pairs]
    return cohen_kappa_score(truth, readings, weights="quadratic", labels=LABELS)


def test_hand_computed():
    assert quadratic_kappa([(0, 0), (1, 1), (2, 1), (3, 3)]) == Fraction(9, 10)


def test_matches_scikit_learn():
    draw = random.Random(20261028)
    for _ in range(200):
        count = draw.randint(2, 40)
        pairs = [(draw.randint(0, 8), draw.randint(0, 8)) for _ in range(count)]
        ours = quadratic_kappa(pairs)
        assert ours is not None, pairs
        assert abs(float(ours) - sklearn_kappa(pairs)) <= 1e-9, pairs


def test_undefined_matches_scikit_learn_nan():
    pairs = [(3, 3), (3, 3)]
    assert quadratic_kappa(pairs) is None
    # scikit-learn warns, then gives its replace_undefined_by default, NaN.
    with pytest.warns(UndefinedMetricWarning):
        assert math.isnan(sklearn_kappa(pairs))


def test_scikit_learn_drops_values_outside_labels():
    # Why C405 maps "no flood seen" to 0: scikit-learn drops -1 without a word.
    pairs = [(4, -1), (4, 4), (2, 2), (6, 5)]
    assert sklearn_kappa(pairs) == sklearn_kappa(pairs[1:])


def test_values_outside_the_levels_raise():
    # So a value can't be dropped unseen, as scikit-learn would drop it.
    for pairs in ([(4, -1)], [(9, 4)]):
        with pytest.raises(ValueError):
            quadratic_kappa(pairs)


def test_no_flood_seen_counts_as_below_gutter(tmp_path):
    scores = score_set_a(load_set_a(tmp_path, HAND_SET), "landmark")
    pairs = [(4, 4), (4, 3), (5, 0), (2, 5), (0, 0), (7, 7)]
    assert scores.kappa == quadratic_kappa(pairs)
    assert scores.kappa_n == 6
