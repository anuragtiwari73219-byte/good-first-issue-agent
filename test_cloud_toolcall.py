import os
import sys
import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types

MODEL = "gemma-4-26b-a4b-it"


def get_repository_info(owner, repo):
    if not owner or not repo:
        raise ValueError("Owner and repository are required.")

    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Good-First-Issue-Agent",
    }

    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()

    return {
        "name": data.get("full_name"),
        "description": data.get("description"),
        "stars": data.get("stargazers_count"),
        "language": data.get("language"),
        "url": data.get("html_url"),
    }


def main():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("ERROR: GEMINI_API_KEY not found in .env")
        return 1

    tool = types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_repository_info",
                description="Fetch actual information about a public GitHub repository.",
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "owner": {"type": "STRING"},
                        "repo": {"type": "STRING"},
                    },
                    "required": ["owner", "repo"],
                },
            )
        ]
    )

    client = genai.Client(api_key=api_key)

    print("Step 1: Asking Gemma 4 to call the tool...")

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=(
                "Use get_repository_info to fetch the GitHub repository "
                "pallets/flask. Set owner to pallets and repo to flask."
            ),
            config=types.GenerateContentConfig(
                tools=[tool],
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode="AUTO"
                    )
                ),
            ),
        )
    except Exception as exc:
        print(f"MODEL API ERROR: {type(exc).__name__}: {exc}")
        return 1

    call = None

    for candidate in response.candidates or []:
        if candidate.content:
            for part in candidate.content.parts or []:
                if part.function_call:
                    call = part.function_call
                    break
        if call:
            break

    if not call:
        print("ERROR: Model did not return a function call.")
        print("Response:", response.text or "(No text response)")
        return 1

    if call.name != "get_repository_info":
        print("ERROR: Unexpected function:", call.name)
        return 1

    args = dict(call.args or {})
    owner = args.get("owner")
    repo = args.get("repo")

    if not owner or not repo:
        print("ERROR: Missing owner or repository name:", args)
        return 1

    print("Step 2: Tool call received.")
    print("Function:", call.name)
    print("Arguments:", args)

    print("\nStep 3: Python is calling the GitHub API...")

    try:
        result = get_repository_info(owner, repo)
    except requests.RequestException as exc:
        print("GITHUB API ERROR:", exc)
        return 1
    except ValueError as exc:
        print("VALIDATION ERROR:", exc)
        return 1

    print("\nSUCCESS: Real GitHub data received!")
    print("Repository:", result["name"])
    print("Description:", result["description"])
    print("Stars:", result["stars"])
    print("Language:", result["language"])
    print("URL:", result["url"])

    return 0


if __name__ == "__main__":
    sys.exit(main())
