import requests
from agent import github_headers

GITHUB_API = "https://api.github.com"


def discover_beginner_issues(language="Python", limit=10):
    query = f'is:issue is:open label:"good first issue" language:{language}'

    response = requests.get(
        f"{GITHUB_API}/search/issues",
        headers=github_headers(),
        params={
            "q": query,
            "per_page": min(limit, 100),
            "sort": "updated",
            "order": "desc",
        },
        timeout=20,
    )

    response.raise_for_status()
    data = response.json()
    results = []

    for item in data.get("items", []):
        if "pull_request" in item:
            continue

        repository_url = item.get("repository_url", "")
        repository = repository_url.removeprefix(f"{GITHUB_API}/repos/")

        results.append({
            "repository": repository,
            "number": item.get("number"),
            "title": item.get("title"),
            "url": item.get("html_url"),
            "state": item.get("state"),
            "labels": [
                label.get("name", "")
                for label in item.get("labels", [])
            ],
        })

    return {
        "query": query,
        "total_matching_results": data.get("total_count", 0),
        "issues": results,
    }


if __name__ == "__main__":
    try:
        result = discover_beginner_issues()

        print("\nGOOD FIRST ISSUE AGENT")
        print("=" * 55)
        print("Search:", result["query"])
        print("Total matching results:", result["total_matching_results"])
        print("Issues received:", len(result["issues"]))

        for index, issue in enumerate(result["issues"], start=1):
            print(f"\n{index}. {issue['repository']} #{issue['number']}")
            print("Title:", issue["title"])
            print("Labels:", ", ".join(issue["labels"]) or "None")
            print("Status:", issue["state"])
            print("URL:", issue["url"])

    except requests.RequestException as error:
        print("GitHub API request failed:", error)

    except (ValueError, KeyError) as error:
        print("Could not process GitHub response:", error)
