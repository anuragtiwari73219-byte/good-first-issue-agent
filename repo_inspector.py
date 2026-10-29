import os
import base64
import requests
from dotenv import load_dotenv


# Load environment variables from .env
load_dotenv()

GITHUB_API = "https://api.github.com"
USER_AGENT = "Good-First-Issue-Agent"

MAX_FILES_LIMIT = 100
MAX_MATCHES = 50
REQUEST_TIMEOUT = 20


def get_github_headers():
    """Prepare headers for authenticated GitHub API requests."""

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
    }

    token = os.getenv("GITHUB_TOKEN")

    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers


def get_python_files(owner, repo):
    """Return Python file paths from a GitHub repository."""

    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/HEAD"

    response = requests.get(
        url,
        headers=get_github_headers(),
        params={"recursive": "1"},
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()
    data = response.json()

    if data.get("truncated"):
        raise ValueError(
            "GitHub returned an incomplete repository tree."
        )

    return [
        item["path"]
        for item in data.get("tree", [])
        if item.get("type") == "blob"
        and item.get("path", "").endswith(".py")
    ]


def get_file_content(owner, repo, path):
    """Fetch and decode a file from GitHub."""

    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"

    response = requests.get(
        url,
        headers=get_github_headers(),
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()
    data = response.json()

    if data.get("encoding") != "base64":
        raise ValueError(f"Unsupported file encoding: {path}")

    if not data.get("content"):
        raise ValueError(f"Empty file content: {path}")

    content = base64.b64decode(data["content"])

    return content.decode("utf-8")


def search_github_code(owner, repo, search_term):
    """
    Ask GitHub Code Search to find files containing the search term.

    Returns matching file paths.
    Raises an exception if the search API is unavailable.
    """

    url = f"{GITHUB_API}/search/code"

    response = requests.get(
        url,
        headers=get_github_headers(),
        params={
            "q": f"{search_term} repo:{owner}/{repo}",
            "per_page": 100,
        },
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    return list(
        dict.fromkeys(
            item["path"]
            for item in data.get("items", [])
            if item.get("path", "").endswith(".py")
        )
    )


def find_matching_lines(owner, repo, paths, search_term):
    """Fetch selected files and return lines containing the search term."""

    term = search_term.casefold()
    results = []
    files_checked = 0

    for path in paths:
        try:
            content = get_file_content(owner, repo, path)

        except (
            requests.RequestException,
            ValueError,
            UnicodeDecodeError,
        ):
            continue

        files_checked += 1

        for line_number, line in enumerate(
            content.splitlines(),
            start=1,
        ):
            if term in line.casefold():
                results.append({
                    "path": path,
                    "line": line_number,
                    "text": line.strip(),
                })

                if len(results) >= MAX_MATCHES:
                    return results, files_checked

    return results, files_checked


def search_repository_code(owner, repo, search_term, max_files=100):
    """
    Search repository Python code.

    First attempts GitHub Code Search.
    If that API is unavailable, falls back to a limited scan of
    Python files, prioritizing paths that match search-term keywords.
    """

    if not isinstance(owner, str) or not owner.strip():
        raise ValueError("Repository owner cannot be empty.")

    if not isinstance(repo, str) or not repo.strip():
        raise ValueError("Repository name cannot be empty.")

    if not isinstance(search_term, str) or not search_term.strip():
        raise ValueError("Search term cannot be empty.")

    if not isinstance(max_files, int) or isinstance(max_files, bool):
        raise ValueError("max_files must be an integer.")

    if not 1 <= max_files <= MAX_FILES_LIMIT:
        raise ValueError(
            f"max_files must be between 1 and {MAX_FILES_LIMIT}."
        )

    owner = owner.strip()
    repo = repo.strip()
    search_term = search_term.strip()

    search_method = "github_code_search"

    try:
        candidate_paths = search_github_code(
            owner,
            repo,
            search_term,
        )

        selected_paths = candidate_paths[:max_files]

    except requests.RequestException:
        # Code Search may require permissions or be rate-limited.
        # Fall back to the repository tree and a bounded file scan.
        search_method = "limited_file_scan"

        all_paths = get_python_files(owner, repo)

        words = [
            word.casefold()
            for word in search_term.replace("_", " ").split()
            if len(word) > 2
        ]

        def path_score(path):
            lowered = path.casefold()
            return sum(word in lowered for word in words)

        selected_paths = sorted(
            all_paths,
            key=path_score,
            reverse=True,
        )[:max_files]

    matches, files_checked = find_matching_lines(
        owner,
        repo,
        selected_paths,
        search_term,
    )

    return {
        "repository": f"{owner}/{repo}",
        "search_term": search_term,
        "search_method": search_method,
        "files_checked": files_checked,
        "matches": matches,
    }


if __name__ == "__main__":
    print("Good First Issue Agent - Repository Inspector")
    print("-" * 50)

    owner = input("GitHub owner: ").strip()
    repo = input("Repository name: ").strip()
    search_term = input("Search term: ").strip()

    try:
        result = search_repository_code(
            owner,
            repo,
            search_term,
            max_files=20,
        )

        print("\nRepository:", result["repository"])
        print("Search term:", result["search_term"])
        print("Search method:", result["search_method"])
        print("Files checked:", result["files_checked"])
        print("Matches found:", len(result["matches"]))

        for match in result["matches"]:
            print(
                f'{match["path"]}:{match["line"]} - '
                f'{match["text"]}'
            )

    except requests.HTTPError as exc:
        print("\nGitHub API error:", exc)

    except requests.RequestException as exc:
        print("\nNetwork error:", exc)

    except ValueError as exc:
        print("\nInput or repository error:", exc)