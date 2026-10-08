import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import analyse_text

import unittest

class AnalysisRulesTest(unittest.TestCase):
    def test_overused_words_ignore_editorial_function_words(self):
        text = (
            "dragon dragon dragon dragon. "
            "I I I I. "
            "the the the the. "
            "and and and and. "
            "was was was was. "
            "can't can't can't can't."
        )
        result = analyse_text(text)
        words = {item["word"]: item["count"] for item in result["words"]}
        self.assertEqual(words.get("dragon"), 4)
        self.assertNotIn("i", words)
        self.assertNotIn("the", words)
        self.assertNotIn("and", words)
        self.assertNotIn("was", words)
        self.assertNotIn("can't", words)
        self.assertNotIn("could've", words)

    def test_passive_voice_with_explicit_agent_is_flagged(self):
        result = analyse_text("The ball was caught by the dog.")
        self.assertEqual(len(result["passive"]), 1)
        self.assertEqual(result["passive"][0]["confidence"], "high")
        self.assertIn("explicit agent", result["passive"][0]["reason"])

    def test_active_voice_is_not_flagged_as_passive(self):
        result = analyse_text("The dog caught the ball.")
        self.assertEqual(result["passive"], [])

    def test_fast_pacing_is_flagged(self):
        result = analyse_text(
            "He ran. She screamed. The door slammed. "
            "The lights went out. They fled."
        )
        reasons = [item["reason"] for item in result["pacing"]]
        self.assertTrue(any("Too fast" in reason for reason in reasons))

    def test_slow_pacing_is_flagged(self):
        result = analyse_text(
            "The old room was incredibly quiet and strangely beautiful, "
            "with dusty shelves, faded curtains, cracked frames, and pale light "
            "resting across every surface. "
            "She looked around the room carefully, noticing the delicate patterns "
            "in the wallpaper and the intricate carvings along the wooden cabinet. "
            "The silence seemed almost impossibly deep, strangely calm, and "
            "completely removed from the busy world outside. "
            "She spoke quietly about the room and the things she remembered, "
            "describing each detail in careful, repetitive language."
        )
        reasons = [item["reason"] for item in result["pacing"]]
        self.assertTrue(any("Too slow" in reason for reason in reasons))

    def test_flat_dynamics_is_flagged(self):
        result = analyse_text(
            "He walked into the room slowly. "
            "He looked around the room slowly. "
            "He touched the table slowly. "
            "He checked the window slowly. "
            "He watched the hallway slowly. "
            "He listened to the house slowly. "
            "He waited beside the door slowly. "
            "He stared at the ceiling slowly."
        )
        reasons = [item["reason"] for item in result["pacing"]]
        self.assertTrue(any("Flat dynamics" in reason for reason in reasons))

    def test_word_count_includes_function_words(self):
        result = analyse_text("I am a writer and you are here.")
        self.assertEqual(result["word_count"], 8)


if __name__ == "__main__":
    unittest.main()
