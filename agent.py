import json
import os
import re
import sys
import time
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types
from repo_inspector import search_repository_code


MODEL = "gemma-4-26b-a4b-it"
GITHUB_API = "https://api.github.com"
USER_AGENT = "Good-First-Issue-Agent"
MAX_ISSUES_FOR_AI = 25


def github_headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def validate_owner_repo(owner, repo):
    if not isinstance(owner, str) or not re.fullmatch(r"[A-Za-z0-9-]+", owner):
        raise ValueError("Invalid GitHub owner.")
    if not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid GitHub repository name.")


def parse_github_url(repo_url):
    if not isinstance(repo_url, str):
        raise ValueError("Please provide a GitHub repository URL.")

    parsed = urlparse(repo_url.strip())
    if (
        parsed.scheme not in ("https", "http")
        or parsed.hostname != "github.com"
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Please provide a valid github.com repository URL.")

    parts = parsed.path.strip("/").split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError(
            "URL must look like https://github.com/owner/repository"
        )

    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    validate_owner_repo(owner, repo)
    return owner, repo


def get_repository_info(owner, repo):
    validate_owner_repo(owner, repo)
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    response = requests.get(url, headers=github_headers(), timeout=20)
    response.raise_for_status()
    data = response.json()

    return {
        "name": data.get("full_name"),
        "description": data.get("description"),
        "stars": data.get("stargazers_count"),
        "language": data.get("language"),
        "url": data.get("html_url"),
    }


def get_repository_issues(owner, repo):
    """Fetch open GitHub issues across multiple pages, excluding pull requests."""
    validate_owner_repo(owner, repo)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues"
    headers = github_headers()

    issues = []
    per_page = 100
    max_pages = 5

    for page in range(1, max_pages + 1):
        params = {
            "state": "open",
            "per_page": per_page,
            "page": page,
            "sort": "updated",
            "direction": "desc",
        }
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list):
            raise ValueError("GitHub returned an unexpected issues response.")

        if not data:
            break

        for item in data:
            # GitHub's Issues API also returns pull requests; exclude them.
            if "pull_request" in item:
                continue

            issues.append({
                "number": item.get("number"),
                "title": item.get("title"),
                "body": (item.get("body") or "")[:800],
                "labels": [
                    label.get("name", "")
                    for label in item.get("labels", [])
                ],
                "comments": item.get("comments", 0),
                "url": item.get("html_url"),
                "state": item.get("state"),
            })

        # No further pages exist if GitHub returned fewer than requested.
        if len(data) < per_page:
            break

    return issues


def get_repository_data(owner, repo):
    """Fetch verified repository metadata and a compact list of open issues."""
    info = get_repository_info(owner, repo)
    issues = get_repository_issues(owner, repo)
    return {
        "repository": info,
        "open_issue_count_returned": len(issues),
        "issues_for_analysis": issues[:MAX_ISSUES_FOR_AI],
        "note": (
            "Only the listed issues may be recommended. "
            "Do not invent issue numbers, labels, titles, or URLs."
        ),
    }


def verify_issue(owner, repo, issue_number):
    validate_owner_repo(owner, repo)
    if (
        isinstance(issue_number, bool)
        or not isinstance(issue_number, int)
        or issue_number <= 0
    ):
        return {"verified": False, "reason": "Issue number must be positive."}

    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}"
    try:
        response = requests.get(url, headers=github_headers(), timeout=20)
        if response.status_code == 404:
            return {"verified": False, "reason": "Issue not found or not public."}
        if response.status_code == 403:
            return {
                "verified": False,
                "reason": "GitHub denied the request or the API rate limit was reached.",
            }
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as error:
        return {"verified": False, "reason": f"GitHub request failed: {error}"}
    except ValueError:
        return {"verified": False, "reason": "GitHub returned invalid JSON."}

    expected_repo = f"{owner}/{repo}".casefold()
    actual_repo = (
        data.get("repository_url", "")
        .removeprefix(f"{GITHUB_API}/repos/")
        .casefold()
    )
    if actual_repo != expected_repo:
        return {"verified": False, "reason": "Repository did not match."}
    if data.get("number") != issue_number:
        return {"verified": False, "reason": "Issue number did not match."}
    if "pull_request" in data:
        return {"verified": False, "reason": "This item is a pull request."}

    state = data.get("state")
    canonical_url = data.get("html_url", "")
    parsed_url = urlparse(canonical_url)
    expected_path = f"/{owner}/{repo}/issues/{issue_number}"
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "github.com"
        or parsed_url.path.casefold() != expected_path.casefold()
    ):
        return {"verified": False, "reason": "Issue URL did not match."}

    return {
        "verified": True,
        "number": issue_number,
        "title": data.get("title"),
        "url": canonical_url,
        "state": state,
        "is_open": state == "open",
        "labels": [label.get("name", "") for label in data.get("labels", [])],
    }


def create_tools():
    """Declare the GitHub data and Python code-search tools for Gemma."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_repository_data",
                description=(
                    "Fetch the selected GitHub repository metadata and its "
                    "real open issues. Pull requests are excluded."
                ),
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "owner": {"type": "STRING"},
                        "repo": {"type": "STRING"},
                    },
                    "required": ["owner", "repo"],
                },
            ),
            types.FunctionDeclaration(
                name="search_repository_code",
                description=(
                    "Search Python source code in the selected GitHub "
                    "repository for a specific function, class, variable, "
                    "or phrase. Use only when the user provided a search term."
                ),
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "owner": {"type": "STRING"},
                        "repo": {"type": "STRING"},
                        "search_term": {
                            "type": "STRING",
                            "description": "A specific function, class, variable, or phrase to find.",
                        },
                    },
                    "required": ["owner", "repo", "search_term"],
                },
            ),
        ]
    )


def execute_tool(name, args, expected_owner, expected_repo):
    owner = args.get("owner")
    repo = args.get("repo")

    # Tools may only access the repository explicitly selected by the user.
    if (
        not isinstance(owner, str)
        or not isinstance(repo, str)
        or owner.casefold() != expected_owner.casefold()
        or repo.casefold() != expected_repo.casefold()
    ):
        return {"error": "Tool request did not match the selected repository."}

    try:
        if name == "get_repository_data":
            return get_repository_data(expected_owner, expected_repo)

        if name == "search_repository_code":
            search_term = args.get("search_term")
            if not isinstance(search_term, str) or not search_term.strip():
                return {"error": "A non-empty search_term is required."}
            if len(search_term.strip()) > 100:
                return {"error": "Search term must be 100 characters or fewer."}

            # Bound the scan to keep requests and results manageable.
            return search_repository_code(
                expected_owner,
                expected_repo,
                search_term.strip(),
                max_files=30,
            )

        return {"error": "Unknown tool requested."}

    except requests.RequestException as error:
        return {"error": f"GitHub API request failed: {error}"}
    except (ValueError, TypeError, UnicodeDecodeError) as error:
        return {"error": f"Data validation failed: {error}"}


def verify_recommendations(text, owner, repo, source_issues):
    """Verify AI-mentioned issues against both fetched data and GitHub's live API."""
    # Markdown links often end with a closing parenthesis, so allow common
    # punctuation after the issue number instead of silently missing those URLs.
    pattern = re.compile(
        rf"https?://(?:www\.)?github\.com/{re.escape(owner)}/"
        rf"{re.escape(repo)}/issues/(\d+)(?=$|[/?#)\]\s.,])",
        re.IGNORECASE,
    )
    issue_numbers = list(dict.fromkeys(
        int(match.group(1)) for match in pattern.finditer(text)
    ))

    if not issue_numbers:
        print("\nNo standard issue URLs found to verify.")
        return []

    source_by_number = {}
    for issue in source_issues or []:
        number = issue.get("number")
        if isinstance(number, int):
            source_by_number[number] = issue

    print(f"\nIssue URLs detected in AI response: {len(issue_numbers)}")
    print(f"Issues available in fetched GitHub data: {len(source_by_number)}")
    print("\n" + "=" * 55)
    print("       RECOMMENDATION VERIFICATION")
    print("=" * 55)

    verified_issues = []
    # The model is asked for at most five recommendations; check each detected
    # recommendation rather than silently verifying only the first URL match.
    for number in issue_numbers[:5]:
        print(f"\nChecking issue #{number}...")

        source_issue = source_by_number.get(number)
        if source_issue is None:
            print(
                "REJECTED: This issue was not in the GitHub issue data supplied "
                "to the AI, so it cannot be accepted as a grounded recommendation."
            )
            continue

        result = verify_issue(owner, repo, number)
        if not result["verified"]:
            print("REJECTED:", result["reason"])
            continue
        if not result["is_open"]:
            print("REJECTED: Issue is not open.")
            continue

        # Keep the API's canonical title/URL/state and use the fetched issue
        # details as a consistency check against hallucinated metadata.
        source_title = source_issue.get("title")
        if source_title and result.get("title") != source_title:
            print("REJECTED: Issue title changed since the analysis data was fetched.")
            continue

        verified_issues.append(result)
        print("VERIFIED: Issue was in the fetched data, exists, and is open.")

    return verified_issues


def main():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found in .env")
        return 1

    print("=" * 55)
    print("       GOOD FIRST ISSUE AGENT")
    print("=" * 55)

    repo_url = input("\nEnter GitHub repository URL: ").strip()
    try:
        owner, repo = parse_github_url(repo_url)
    except ValueError as error:
        print(f"\nInvalid repository URL: {error}")
        return 1

    print(f"\nRepository selected: {owner}/{repo}")
    search_term = input(
        "\nOptional: enter a Python function/class/phrase to search for "
        "(press Enter to skip): "
    ).strip()
    if len(search_term) > 100:
        print("Search term must be 100 characters or fewer.")
        return 1

    print("\nFetching repository information and open issues...")
    if search_term:
        print(f"Python code search requested: {search_term}")

    client = genai.Client(api_key=api_key)
    tools = create_tools()

    # Gemma must fetch real repository data. If the user supplied a search
    # term, it must also use the bounded Python code-search tool.
    prompt = (
        "You are Good First Issue Agent. For the selected repository "
        f"{owner}/{repo}, call get_repository_data exactly once using "
        "the provided owner and repo. Do not recommend issues until the "
        "real GitHub data has been returned. "
    )
    if search_term:
        prompt += (
            "The user also requested a Python code search for this exact term: "
            f"{search_term!r}. Call search_repository_code exactly once using "
            f"owner={owner!r}, repo={repo!r}, and search_term={search_term!r}. "
            "Do not change the search term."
        )
    contents = [prompt]
    tool_config = types.GenerateContentConfig(tools=[tools])

    print("Agent thinking... (tool request)")
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=tool_config,
        )
    except Exception as error:
        print("\nAI tool-request failed.")
        print("Error type:", type(error).__name__)
        print("Error details:", repr(error))
        print("This failure occurred during the initial tool-request.")
        return 1

    if not response.candidates or not response.candidates[0].content:
        print("The model returned no candidate content.")
        return 1

    model_content = response.candidates[0].content
    function_calls = [
        part.function_call
        for part in (model_content.parts or [])
        if getattr(part, "function_call", None)
    ]

    if not function_calls:
        print("\nThe model did not request the data tool.")
        print("Model response:", response.text or "(no text response)")
        return 1

    contents.append(model_content)
    tool_results = []
    executed_tool_names = set()

    for call in function_calls:
        print(f"Tool requested: {call.name}")
        args = dict(call.args or {})
        result = execute_tool(call.name, args, owner, repo)
        tool_results.append(result)
        executed_tool_names.add(call.name)
        print(f"Tool completed: {call.name}")

        contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part.from_function_response(
                        name=call.name,
                        response={"result": result},
                    )
                ],
            )
        )

    # Some model responses may emit only one of the requested calls. Ensure
    # required data operations still run, without repeating successful calls.
    if "get_repository_data" not in executed_tool_names:
        print("Running required repository-data tool...")
        result = execute_tool(
            "get_repository_data",
            {"owner": owner, "repo": repo},
            owner,
            repo,
        )
        tool_results.append(result)

    if search_term and "search_repository_code" not in executed_tool_names:
        print("Running requested Python code search...")
        result = execute_tool(
            "search_repository_code",
            {"owner": owner, "repo": repo, "search_term": search_term},
            owner,
            repo,
        )
        tool_results.append(result)

    # IMPORTANT: Do not replay the model's function-call transcript in the
    # analysis request. Send a fresh text-only request with the actual tool data.
    analysis_prompt = (
        "You are Good First Issue Agent. Analyze the JSON tool results below.\n"
        "The result with repository metadata and issues is the source of truth. "
        "Recommend up to 5 potentially beginner-friendly OPEN issues. Prefer "
        "good first issue/help wanted labels, but do not assume an issue is "
        "easy just because it is open. For each recommendation, explain why "
        "it may suit a beginner and give practical first steps. Use only the "
        "provided issue numbers, titles, labels and URLs. Never invent data. "
        "Recommend only issues that appear in issues_for_analysis. End with "
        "a section named 'Issue URLs to verify' containing each recommended "
        "canonical GitHub issue URL on its own line (not inside Markdown links). "
        "If Python code-search results are present, summarize relevant matches "
        "using the exact file paths and line numbers returned; do not claim "
        "that code was found if the matches list is empty. If no suitable "
        "issues are present, say so. End with exact issue URLs.\n\n"
        "GITHUB_TOOL_RESULTS_JSON:\n"
        + json.dumps(tool_results, ensure_ascii=False)
    )

    print("Agent thinking... (issue analysis)")
    analysis_response = None
    last_error = None
    # Try Gemma first, with short retries for transient server-side errors.
    for attempt in range(1, 3):
        try:
            analysis_response = client.models.generate_content(
                model=MODEL,
                contents=analysis_prompt,
                config=types.GenerateContentConfig(),
            )
            if analysis_response.text:
                break
        except Exception as error:
            last_error = error
            print(f"Analysis attempt {attempt}/2 failed: {type(error).__name__}")
            if attempt < 2:
                time.sleep(2)

    # If Gemma still returns a server error, use a current Gemini Flash model
    # for the plain-text analysis. GitHub data has already been fetched safely.
    if analysis_response is None or not analysis_response.text:
        fallback_model = "gemini-3.6-flash"
        print(f"Trying fallback analysis model: {fallback_model}")
        try:
            analysis_response = client.models.generate_content(
                model=fallback_model,
                contents=analysis_prompt,
                config=types.GenerateContentConfig(),
            )
        except Exception as error:
            print("\nAI analysis request failed on both models.")
            print("Gemma error:", repr(last_error))
            print("Fallback error:", repr(error))
            print("GitHub data was fetched successfully; only AI analysis failed.")
            return 1

    final_text = analysis_response.text or ""
    print("\n" + "=" * 55)
    print("       AI ANALYSIS")
    print("=" * 55)
    print(final_text if final_text else "The model returned no text analysis.")

    source_issues = []
    for result in tool_results:
        if isinstance(result, dict) and isinstance(result.get("issues_for_analysis"), list):
            source_issues = result["issues_for_analysis"]
            break

    verified_issues = verify_recommendations(
        final_text, owner, repo, source_issues
    )

    print("\n" + "=" * 55)
    print("       VERIFIED OPEN ISSUES")
    print("=" * 55)
    if not verified_issues:
        print("No verified open issues were found in the AI recommendations.")
        return 0

    for index, issue in enumerate(verified_issues, start=1):
        print(f"\n{index}. {issue['title']}")
        print(f"   Issue: #{issue['number']}")
        print(f"   URL: {issue['url']}")
        print("   Labels: " + (", ".join(issue["labels"]) or "None"))
        print(f"   Status: {issue['state']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
