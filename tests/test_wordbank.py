import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from wordbank import bank_problems, entry_problems, norm, retire_overflow  # noqa: E402
import generate_words as gen  # noqa: E402


def entry(word, hints=("Alpha", "Bravo", "Charlie", "Delta"), added=""):
    e = {"word": word, "hints": list(hints)}
    if added:
        e["added"] = added
    return e


def bank(*cats):
    return {"updated": "2026-11-12T00:00:00Z",
            "categories": [{"id": cid, "emo": "x", "name": cid.title(), "desc": "d", "words": words}
                           for cid, words in cats]}


class EntryRules(unittest.TestCase):
    def test_good_entry(self):
        self.assertEqual(entry_problems(entry("Taylor Swift", ["Bracelets", "Eras", "Travis", "Cats"])), [])

    def test_needs_four_hints(self):
        self.assertTrue(entry_problems(entry("Drake", ["Owl", "Toronto", "Hotline"])))

    def test_hint_containing_the_word_is_a_giveaway(self):
        problems = entry_problems(entry("Pickleball", ["Pickle", "Paddle", "Kitchen", "Dink"]))
        self.assertEqual(problems, [])  # "Pickle" isn't a separate token of "Pickleball"
        problems = entry_problems(entry("Stanley Cup", ["Stanley", "Ice", "Trophy", "Sip"]))
        self.assertTrue(any("gives the word away" in p for p in problems))

    def test_repeated_hint(self):
        self.assertTrue(any("repeated" in p for p in entry_problems(entry("X Games", ["Ramp", "ramp", "Air", "Snow"]))))

    def test_long_hint(self):
        self.assertTrue(entry_problems(entry("Prom", ["A very long hint phrase", "Corsage", "Limo", "Dance"])))


class BankRules(unittest.TestCase):
    def test_same_word_in_two_categories(self):
        b = bank(("a", [entry("The Office")]), ("b", [entry("office")]))
        self.assertTrue(any("also in a" in p for p in bank_problems(b)))

    def test_retired_word_cannot_return(self):
        b = bank(("a", [entry("Fidget Spinner")]))
        self.assertTrue(bank_problems(b, [{"word": "fidget spinner"}]))

    def test_norm_ignores_case_accents_punctuation(self):
        self.assertEqual(norm("Beyoncé"), norm("beyonce"))
        self.assertEqual(norm("The Bear"), norm("Bear"))


class Retiring(unittest.TestCase):
    def test_oldest_trends_retire_first(self):
        words = [entry(f"W{i}", added=f"2026-11-{i:02d}T00:00:00Z") for i in range(1, 63)]
        words.append(entry("Seed"))  # original words have no date and go first
        b = bank(("trends", words))
        retired = []
        gone = retire_overflow(b, retired, "2026-12-01T00:00:00Z")
        self.assertEqual(len(b["categories"][0]["words"]), 60)
        self.assertEqual([g["word"] for g in gone], ["W1", "W2", "Seed"])
        self.assertEqual(retired, gone)


class Generating(unittest.TestCase):
    def test_tagged_json(self):
        self.assertEqual(gen.tagged_json('blah <words>[{"word":"A"}]</words> x', "words"), [{"word": "A"}])
        with self.assertRaises(ValueError):
            gen.tagged_json("no tags", "words")

    def test_filter_new_drops_taken_and_bad(self):
        taken = {norm("Drake")}
        kept = gen.filter_new([
            {"word": "Drake", "hints": ["Owl", "Toronto", "Hotline", "Six"]},
            {"word": "Doechii", "hints": ["Swamp", "Florida", "Anxiety", "Grammy"]},
            {"word": "Doechii", "hints": ["Swamp", "Florida", "Anxiety", "Grammy"]},
            {"word": "Labubu", "hints": ["Labubu", "Keychain", "Monster", "Blind Box"]},
            "nonsense",
        ], taken)
        self.assertEqual([k["word"] for k in kept], ["Doechii"])

    def test_review_fix_and_drop(self):
        entries = [entry("A1"), entry("B2"), entry("C3")]
        out = gen.apply_review(entries, [
            {"i": 0, "verdict": "ok"},
            {"i": 1, "verdict": "drop", "reason": "unknown"},
            {"i": 2, "verdict": "fix", "hints": ["One", "Two", "Three", "Four"]},
        ])
        self.assertEqual([(e["word"], e["hints"][0]) for e in out], [("A1", "Alpha"), ("C3", "One")])

    def test_review_fix_that_still_breaks_rules_is_dropped(self):
        out = gen.apply_review([entry("Stanley Cup")], [{"i": 0, "verdict": "fix", "hints": ["Stanley", "B", "C", "D"]}])
        self.assertEqual(out, [])


class RealBank(unittest.TestCase):
    def test_words_json_passes(self):
        from wordbank import load_bank, load_retired
        self.assertEqual(bank_problems(load_bank(), load_retired()), [])


if __name__ == "__main__":
    unittest.main()
