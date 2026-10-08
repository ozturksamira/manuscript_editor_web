import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import analyse_text


ROOT = Path(__file__).resolve().parent.parent


class AnalysisParityTest(unittest.TestCase):
    def test_proper_nouns_are_not_overused_word_flags(self):
        value = (
            "John walked through London. John stopped in London. "
            "John looked back at London. John left London. "
            "The river crossed the valley. The river narrowed. "
            "The river widened. The river flooded the valley."
        )
        result = analyse_text(value)
        flagged = {item["word"] for item in result["words"]}
        self.assertNotIn("john", flagged)
        self.assertNotIn("london", flagged)
        self.assertIn("river", flagged)

    def test_sentence_initial_common_words_stay_eligible(self):
        value = (
            "River flooded the valley. River narrowed overnight. "
            "River widened after the storm. River overflowed the banks. "
            "House stood at the end of the road. House needed repairs. "
            "House looked empty at dusk. House remained locked. "
            "Chapter opened with a warning. Chapter ended with a question. "
            "Chapter returned to the same mystery. Chapter closed on a cliffhanger."
        )
        result = analyse_text(value)
        flagged = {item["word"] for item in result["words"]}
        self.assertIn("river", flagged)
        self.assertIn("house", flagged)
        self.assertIn("chapter", flagged)

    def test_proper_noun_heuristic_requires_more_than_mid_sentence_capitalization(self):
        value = (
            "The River flowed quietly. The River slowed. "
            "The River turned north. The River reached the sea. "
            "John walked through London. John stopped in London. "
            "John looked back at London. John left London."
        )
        result = analyse_text(value)
        flagged = {item["word"] for item in result["words"]}
        self.assertIn("river", flagged)
        self.assertNotIn("john", flagged)
        self.assertNotIn("london", flagged)

    def test_python_and_browser_analysis_match(self):
        fixtures = [
            "The ball was thrown by John.",
            "He ran. She screamed. The door slammed. The lights went out. They fled.",
            "The old room was incredibly quiet and strangely beautiful, with dusty shelves, faded curtains, cracked frames, and pale light resting across every surface. She looked around the room carefully, noticing the delicate patterns in the wallpaper and the intricate carvings along the wooden cabinet. The silence seemed almost impossibly deep, strangely calm, and completely removed from the busy world outside.",
            "dragon dragon dragon dragon. The dragon watched the door. The dragon walked away.",
            "John walked through London. John stopped in London. John looked back at London. John left London.",
            "The river crossed the valley. The river narrowed. The river widened. The river flooded the valley.",
        ]
        node_script = """
import { analyseText } from './public/analysis.js';
const input = JSON.parse(process.argv[1]);
process.stdout.write(JSON.stringify(input.map(analyseText)));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", node_script, json.dumps(fixtures)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=20,
        )
        browser_results = json.loads(result.stdout)
        python_results = [analyse_text(value) for value in fixtures]
        self.assertEqual(browser_results, python_results)


if __name__ == "__main__":
    unittest.main()