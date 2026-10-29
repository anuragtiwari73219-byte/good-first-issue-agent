from issue_scoring import calculate_issue_score
from test_issue_discovery import discover_beginner_issues
from test_issue_details import get_issue_details


def main():
    result = discover_beginner_issues(limit=3)

    print("\nREAL GITHUB ISSUE SCORING")
    print("=" * 60)

    for item in result["issues"]:
        repository = item["repository"]
        number = item["number"]

        try:
            issue = get_issue_details(repository, number)

        except Exception as error:
            print(f"\nCould not fetch {repository} #{number}: {error}")
            continue

        if not issue:
            print(f"\nSkipping {repository} #{number}: not a regular issue.")
            continue

        score = calculate_issue_score(issue)

        print(f"\nRepository: {repository}")
        print(f"Issue: #{number} - {issue.get('title', '')}")
        print(f"State: {issue.get('state', 'unknown')}")
        print(f"URL: {issue.get('url', '')}")
        print(f"Score: {score['score']}/{score['maximum_score']}")
        print(f"Assessment: {score['estimated_difficulty']}")
        print("Reasons:", "; ".join(score["reasons"]) or "None")
        print("Warnings:", "; ".join(score["warnings"]) or "None")


if __name__ == "__main__":
    main()
