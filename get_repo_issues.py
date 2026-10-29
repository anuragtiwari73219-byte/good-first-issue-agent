import requests


def get_repository_issues(owner, repo):
    """
    Fetch open issues from a GitHub repository.
    Exclude pull requests from the results.
    """

    url = f"https://api.github.com/repos/{owner}/{repo}/issues"

    params = {
        "state": "open",
        "per_page": 30,
        "sort": "updated",
        "direction": "desc"
    }

    headers = {
        "Accept": "application/vnd.github+json"
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    issues = []

    for item in data:

        # GitHub Issues API can also return pull requests.
        # We only want actual issues.
        if "pull_request" in item:
            continue

        issue = {
            "number": item["number"],
            "title": item["title"],
            "body": (item.get("body") or "")[:1500],
            "labels": [
                label["name"]
                for label in item.get("labels", [])
            ],
            "comments": item["comments"],
            "url": item["html_url"]
        }

        issues.append(issue)

    return issues


if __name__ == "__main__":

    owner = "pallets"
    repo = "flask"

    try:
        print(f"Fetching issues from {owner}/{repo}...\n")

        issues = get_repository_issues(owner, repo)

        print(f"Repository: {owner}/{repo}")
        print(f"Total issues fetched: {len(issues)}")
        print()

        if not issues:
            print("No open issues found in this API response.")

        for issue in issues[:5]:
            print(f"Issue #{issue['number']}: {issue['title']}")

            print(
                f"Labels: {', '.join(issue['labels']) or 'No labels'}"
            )

            print(f"Comments: {issue['comments']}")
            print(f"URL: {issue['url']}")
            print("-" * 60)

    except requests.RequestException as error:
        print(f"GitHub API request failed: {error}")

