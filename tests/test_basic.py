
import unittest
from app import split_facts, score, terms
class CoreTests(unittest.TestCase):
    def test_sentence_split(self):
        self.assertGreaterEqual(len(split_facts("The library opens at nine. Students can borrow books.")), 2)
    def test_relevant_terms_score(self):
        value, matched = score("library opening time", "The library opening time is nine in the morning.")
        self.assertGreater(value, 0)
        self.assertIn("library", matched)
    def test_empty_terms(self):
        self.assertEqual(score("the and", "of the and"), (0.0, []))
if __name__ == "__main__": unittest.main()
