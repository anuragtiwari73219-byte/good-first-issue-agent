import os
import re
import sys

import requests
from dotenv import load_dotenv


def verify_issue(owner, repo, issue_number, expected_title=None):
    """
    Verify a GitHub issue using the official GitHub API.

    Checks:
    - Valid owner, repository and issue number
    - Issue exists in the specified repository
    - Response belongs to the expected repository
    - The item is an issue, not a pull request
    - Optional title matches the actual title
    - Current issue state
    """

    if not re.fullmatch(r"[A-Za-z0-9-]+", owner):
        raise ValueError("Invalid GitHub owner.")

    if not re.fullmatch(r"[A-Za-z0-9._-]+", repo):
        raise ValueError("Invalid GitHub repository name.")

    if not isinstance(issue_number, int) or issue_number <= 0:
        raise ValueError("Issue number must be a positive integer.")

    url = (
        f"https://api.github.com/repos/"
        f"{owner}/{repo}/issues/{issue_number}"
    )

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Good-First-Issue-Agent",
    }

    token = os.getenv("GITHUB_TOKEN")

    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.get(
        url,
        headers=headers,
        timeout=15,
    )

    # Handle common API errors clearly.
    if response.status_code == 404:
        return {
            "verified": False,
            "reason": "Issue not found or not publicly accessible.",
        }

    if response.status_code == 403:
        return {
            "verified": False,
            "reason": "GitHub denied the request or rate limit was reached.",
        }

    response.raise_for_status()

    data = response.json()

    actual_title = data.get("title")
    actual_number = data.get("number")
    actual_url = data.get("html_url")
    actual_state = data.get("state")

    expected_url = (
        f"https://github.com/{owner}/{repo}/issues/{issue_number}"
    )

    # Confirm the API returned the expected repository and issue.
    expected_api_url = (
        f"https://api.github.com/repos/"
        f"{owner}/{repo}/issues/{issue_number}"
    )

    if actual_number != issue_number:
        return {
            "verified": False,
            "reason": "Returned issue number does not match.",
        }

    if actual_url != expected_url:
        return {
            "verified": False,
            "reason": "Issue URL does not match the expected repository.",
        }

    # GitHub's Issues API can return pull requests too.
    if "pull_request" in data:
        return {
            "verified": False,
            "reason": "The returned item is a pull request, not an issue.",
        }

    # Check the optional title supplied by the AI.
    if expected_title is not None:
        if actual_title != expected_title:
            return {
                "verified": False,
                "reason": "Issue title does not match GitHub's actual title.",
                "actual_title": actual_title,
            }

    return {
        "verified": True,
        "repository": f"{owner}/{repo}",
        "number": actual_number,
        "title": actual_title,
        "url": actual_url,
        "state": actual_state,
        "is_open": actual_state == "open",
        "reason": (
            "Issue details match GitHub's API response."
        ),
    }


def main():
    load_dotenv()

    print("=" * 55)
    print("       GITHUB ISSUE VERIFIER")
    print("=" * 55)

    owner = input("Repository owner (example: pallets): ").strip()
    repo = input("Repository name (example: flask): ").strip()

    issue_input = input("Issue number (example: 6146): ").strip()

    if not issue_input.isdigit():
        print("ERROR: Issue number must be a positive integer.")
        return 1

    issue_number = int(issue_input)

    try:
        result = verify_issue(
            owner=owner,
            repo=repo,
            issue_number=issue_number,
        )

    except ValueError as error:
        print(f"INPUT ERROR: {error}")
        return 1

    except requests.RequestException as error:
        print(f"GITHUB API ERROR: {error}")
        return 1

    print("\nVerification result:")
    print("-" * 55)

    if not result["verified"]:
        print("VERIFIED: NO")
        print("Reason:", result["reason"])

        if result.get("actual_title"):
            print("Actual title:", result["actual_title"])

        return 1

    print("VERIFIED: YES")
    print("Repository:", result["repository"])
    print("Issue number:", result["number"])
    print("Title:", result["title"])
    print("URL:", result["url"])
    print("Current status:", result["state"])
    print("Currently open:", result["is_open"])
    print("Reason:", result["reason"])

    if not result["is_open"]:
        print(
            "\nNOTE: The issue exists, but it is not currently open."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())

