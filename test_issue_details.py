from test_issue_discovery import discover_beginner_issues

import requests
from agent import github_headers

GITHUB_API = "https://api.github.com"


def get_issue_details(repository, issue_number):
    owner, repo = repository.split("/", 1)

    response = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}",
        headers=github_headers(),
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()

    if "pull_request" in data:
        return None

    return {
        "repository": repository,
        "number": data.get("number"),
        "title": data.get("title"),
        "body": (data.get("body") or "")[:1500],
        "labels": [
            label.get("name", "")
            for label in data.get("labels", [])
        ],
        "url": data.get("html_url"),
        "state": data.get("state"),
    }


if __name__ == "__main__":
    try:
        result = discover_beginner_issues(limit=3)

        for issue in result["issues"]:
            details = get_issue_details(
                issue["repository"],
                issue["number"],
            )

            if details is None:
                continue

            print("\n" + "=" * 60)
            print(f"{details['repository']} #{details['number']}")
            print("Title:", details["title"])
            print("Labels:", ", ".join(details["labels"]) or "None")
            print("Description:")
            print(details["body"] or "No description provided")
            print("URL:", details["url"])

    except (requests.RequestException, ValueError) as error:
        print("Error:", error)
