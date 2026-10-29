import unittest

from issue_scoring import calculate_issue_score


class TestIssueScoring(unittest.TestCase):

    def test_good_documentation_issue(self):
        issue = {
            "title": "Improve documentation",
            "body": "Add a clear example showing how beginners can use this feature.",
            "labels": ["good first issue", "documentation"],
        }

        result = calculate_issue_score(issue)

        self.assertEqual(result["score"], 12)
        self.assertEqual(result["maximum_score"], 16)
        self.assertEqual(
            result["estimated_difficulty"],
            "potentially beginner-friendly",
        )

    def test_empty_issue(self):
        result = calculate_issue_score({
            "title": "",
            "body": "",
            "labels": [],
        })

        self.assertEqual(result["score"], 0)
        self.assertTrue(result["warnings"])

    def test_missing_fields(self):
        result = calculate_issue_score({})

        self.assertEqual(result["score"], 0)
        self.assertTrue(result["warnings"])

    def test_fixed_label_reduces_score(self):
        issue = {
            "title": "Fix old bug",
            "body": "This issue describes a bug that may already have been resolved.",
            "labels": ["fixed"],
        }

        result = calculate_issue_score(issue)

        self.assertEqual(result["score"], 0)
        self.assertTrue(result["warnings"])

    def test_issue_without_labels(self):
        issue = {
            "title": "Add a simple example",
            "body": "Add a basic example to help users understand this feature.",
            "labels": [],
        }

        result = calculate_issue_score(issue)

        self.assertEqual(result["score"], 5)

    def test_score_stays_within_valid_range(self):
        test_issues = [
            {},
            {"title": "Example", "body": "Short description", "labels": []},
            {
                "title": "Documentation",
                "body": "A" * 200,
                "labels": [
                    "good first issue",
                    "help wanted",
                    "documentation",
                ],
            },
        ]

        for issue in test_issues:
            with self.subTest(issue=issue):
                result = calculate_issue_score(issue)

                self.assertGreaterEqual(result["score"], 0)
                self.assertLessEqual(
                    result["score"],
                    result["maximum_score"],
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
