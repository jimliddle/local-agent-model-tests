import unittest
from workflow import decision_checks


class DecisionTests(unittest.TestCase):
    def value(self, version):
        return {'version': version, 'choice': 'Birch' if version == 1 else None,
                'budget': 9 if version == 1 else 6, 'handwriting_accuracy': None,
                'sources': ['requirements', 'atlas', 'birch-current', 'cedar'],
                'reason': 'Birch meets the initial limits; the reduced budget excludes it.'}

    def test_valid_decisions(self):
        for version in (1, 2):
            self.assertTrue(all(decision_checks(self.value(version), version).values()))

    def test_old_decision_does_not_pass_revision(self):
        self.assertFalse(all(decision_checks(self.value(1), 2).values()))

    def test_invented_accuracy_fails(self):
        value = {**self.value(1), 'handwriting_accuracy': 99}
        self.assertFalse(decision_checks(value, 1)['handwriting_accuracy'])

    def test_missing_evidence_fails(self):
        value = {**self.value(1), 'sources': ['birch-old']}
        self.assertFalse(decision_checks(value, 1)['sources'])

    def test_missing_decision_fails(self):
        self.assertFalse(any(decision_checks(None, 2).values()))

    def test_malformed_sources_fail_without_crashing(self):
        for sources in (None, 'requirements', [{'id': 'requirements'}]):
            self.assertFalse(decision_checks({**self.value(1), 'sources': sources}, 1)['sources'])


if __name__ == '__main__':
    unittest.main()
