"""Runs the page's own scoring function (roundPoints in index.html) under Node."""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

PAGE = (Path(__file__).resolve().parent.parent / "index.html").read_text(encoding="utf-8")
PLAYERS = ["Ann", "Ben", "Cat", "Dan", "Eve"]


def scoring_source():
    start = PAGE.index("const POINTS=")
    end = PAGE.index("function standings(")
    return PAGE[start:end]


def round_points(imps, outcome):
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is needed to run the scoring tests")
    script = scoring_source() + "\nconsole.log(JSON.stringify(roundPoints(%s,%s,%s)));" % (
        json.dumps(PLAYERS), json.dumps(imps), json.dumps({str(k): v for k, v in outcome.items()}))
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


class Scoring(unittest.TestCase):
    def test_undetected_imposter_gets_one(self):
        self.assertEqual(round_points([0], {0: {"caught": False}}),
                         {"Ann": 1, "Ben": 0, "Cat": 0, "Dan": 0, "Eve": 0})

    def test_undetected_and_guessed_gets_two(self):
        self.assertEqual(round_points([0], {0: {"caught": False, "guessed": True}})["Ann"], 2)

    def test_caught_but_guessed_still_gets_the_guess_point(self):
        d = round_points([0], {0: {"caught": True, "guessed": True}})
        self.assertEqual(d, {"Ann": 1, "Ben": 1, "Cat": 1, "Dan": 1, "Eve": 1})

    def test_caught_without_guess_scores_only_the_crew(self):
        d = round_points([0], {0: {"caught": True, "guessed": False}})
        self.assertEqual(d, {"Ann": 0, "Ben": 1, "Cat": 1, "Dan": 1, "Eve": 1})

    def test_two_imposters_scored_separately(self):
        # Ann caught and guessed, Ben got away without guessing: crew gets 1 (for Ann's catch)
        d = round_points([0, 1], {0: {"caught": True, "guessed": True}, 1: {"caught": False}})
        self.assertEqual(d, {"Ann": 1, "Ben": 1, "Cat": 1, "Dan": 1, "Eve": 1})

    def test_guess_toggle_shows_for_every_imposter_and_keeps_its_state(self):
        # The "Guessed word" chip is always shown, and picking Caught/Got away keeps the guess.
        card = PAGE[PAGE.index("function drawScorecard"):PAGE.index("$(\"#sc-save\").onclick")]
        self.assertNotIn("${o.caught?`<button class=\"chip", card)
        self.assertIn('G.outcome[i]={...G.outcome[i],caught:', card)


if __name__ == "__main__":
    unittest.main()
