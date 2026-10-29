import json
import os
import re
import time

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

from agent import (
    MODEL,
    create_tools,
    execute_tool,
    parse_github_url,
    verify_issue,
)

load_dotenv()

st.set_page_config(
    page_title="Good First Issue Agent",
    page_icon="🔎",
    layout="wide",
)

st.title("🔎 Good First Issue Agent")
st.caption(
    "Find potentially beginner-friendly GitHub issues with Gemma 4, "
    "Python code search, and GitHub verification."
)

with st.sidebar:
    st.header("About this agent")
    st.write("1. Fetches real repository information and open issues.")
    st.write("2. Uses Gemma tool calling to request the required tools.")
    st.write("3. Optionally searches Python source code.")
    st.write("4. Verifies recommended issue links before displaying them.")
    st.divider()
    st.caption("Never share your API keys or .env file.")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error(
        "GEMINI_API_KEY was not found. Add it to your project's .env file "
        "and restart Streamlit."
    )
    st.stop()

with st.form("repository_form"):
    repo_url = st.text_input(
        "GitHub repository URL",
        placeholder="https://github.com/pallets/flask",
    )
    search_term = st.text_input(
        "Optional Python code search",
        placeholder="e.g. request, router, Response",
        help="Leave blank to skip code search. Maximum 100 characters.",
    )
    submitted = st.form_submit_button(
        "Find beginner-friendly issues",
        type="primary",
        use_container_width=True,
    )


def verify_recommendations_in_ui(analysis_text, owner, repo, repository_data):
    """Verify only recommendations present in fetched data and still open."""
    pattern = re.compile(
        rf"https?://github\.com/{re.escape(owner)}/"
        rf"{re.escape(repo)}/issues/(\d+)(?:[/?#]|$)",
        re.IGNORECASE,
    )
    numbers = list(
        dict.fromkeys(int(match.group(1)) for match in pattern.finditer(analysis_text))
    )

    fetched_issues = repository_data.get("issues_for_analysis", [])
    fetched_by_number = {
        issue.get("number"): issue
        for issue in fetched_issues
        if isinstance(issue, dict) and isinstance(issue.get("number"), int)
    }

    verified = []
    rejected = []

    for number in numbers[:5]:
        if number not in fetched_by_number:
            rejected.append({
                "number": number,
                "reason": "Issue was not present in the issue data provided to the AI.",
            })
            continue

        result = verify_issue(owner, repo, number)
        if not result.get("verified"):
            rejected.append({
                "number": number,
                "reason": result.get("reason", "GitHub verification failed."),
            })
            continue
        if not result.get("is_open"):
            rejected.append({
                "number": number,
                "reason": "Issue is no longer open.",
            })
            continue

        # Use the API-verified title/URL/state and fetched labels as fallback.
        if not result.get("labels"):
            result["labels"] = fetched_by_number[number].get("labels", [])
        verified.append(result)

    return verified, rejected, len(numbers)


def run_agent(repo_url, search_term):
    owner, repo = parse_github_url(repo_url)

    client = genai.Client(api_key=api_key)
    declared_tools = create_tools()

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

    with st.status("Gemma is requesting repository tools…", expanded=True) as status:
        contents = [prompt]
        tool_config = types.GenerateContentConfig(tools=[declared_tools])

        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=tool_config,
        )

        if not response.candidates or not response.candidates[0].content:
            raise RuntimeError("Gemma returned no tool-request content.")

        model_content = response.candidates[0].content
        function_calls = [
            part.function_call
            for part in (model_content.parts or [])
            if getattr(part, "function_call", None)
        ]

        if not function_calls:
            detail = response.text or "No tool request was returned."
            raise RuntimeError(f"Gemma did not request the required tools. {detail}")

        contents.append(model_content)
        tool_results = []
        executed_tool_names = set()

        for call in function_calls:
            st.write(f"Running tool: `{call.name}`")
            result = execute_tool(
                call.name,
                dict(call.args or {}),
                owner,
                repo,
            )
            tool_results.append(result)
            executed_tool_names.add(call.name)
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

        # Ensure required tools run even if the model requests only one tool.
        if "get_repository_data" not in executed_tool_names:
            st.write("Running required tool: `get_repository_data`")
            result = execute_tool(
                "get_repository_data",
                {"owner": owner, "repo": repo},
                owner,
                repo,
            )
            tool_results.append(result)

        if search_term and "search_repository_code" not in executed_tool_names:
            st.write("Running requested tool: `search_repository_code`")
            result = execute_tool(
                "search_repository_code",
                {"owner": owner, "repo": repo, "search_term": search_term},
                owner,
                repo,
            )
            tool_results.append(result)

        repository_data = next(
            (
                item for item in tool_results
                if isinstance(item, dict)
                and isinstance(item.get("repository"), dict)
                and "issues_for_analysis" in item
            ),
            None,
        )
        if repository_data is None:
            raise RuntimeError(
                "Repository data could not be loaded. Check the GitHub API response."
            )

        analysis_prompt = (
            "You are Good First Issue Agent. Analyze the JSON tool results below.\n"
            "The repository metadata and listed issues are the source of truth. "
            "Recommend up to 5 potentially beginner-friendly OPEN issues. Prefer "
            "good first issue/help wanted labels, but do not assume an issue is "
            "easy just because it is open. For each recommendation, explain why "
            "it may suit a beginner and give practical first steps. Use only the "
            "provided issue numbers, titles, labels and URLs. Never invent data. "
            "If Python code-search results are present, summarize relevant matches "
            "using exact file paths and line numbers returned. If no suitable "
            "issues are present, say so. End with exact issue URLs.\n\n"
            "GITHUB_TOOL_RESULTS_JSON:\n"
            + json.dumps(tool_results, ensure_ascii=False)
        )

        status.update(label="Analyzing issues with AI…", state="running")
        analysis_response = None
        last_error = None

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
                if attempt < 2:
                    time.sleep(2)

        if analysis_response is None or not analysis_response.text:
            fallback_model = "gemini-3.6-flash"
            st.warning(f"Gemma analysis did not return text. Trying {fallback_model}.")
            try:
                analysis_response = client.models.generate_content(
                    model=fallback_model,
                    contents=analysis_prompt,
                    config=types.GenerateContentConfig(),
                )
            except Exception as error:
                raise RuntimeError(
                    "AI analysis failed on the primary and fallback models. "
                    f"Primary error: {last_error!r}; fallback error: {error!r}"
                ) from error

        analysis_text = analysis_response.text or ""
        status.update(label="Repository analysis completed", state="complete")

    verified, rejected, detected_count = verify_recommendations_in_ui(
        analysis_text,
        owner,
        repo,
        repository_data,
    )

    return {
        "owner": owner,
        "repo": repo,
        "repository_data": repository_data,
        "analysis": analysis_text,
        "verified_issues": verified,
        "rejected_issues": rejected,
        "detected_count": detected_count,
        "search_term": search_term,
        "tool_results": tool_results,
    }


if submitted:
    if not repo_url.strip():
        st.error("Please enter a GitHub repository URL.")
        st.stop()
    if len(search_term) > 100:
        st.error("Search term must be 100 characters or fewer.")
        st.stop()

    try:
        owner, repo = parse_github_url(repo_url)
        st.info(f"Repository selected: **{owner}/{repo}**")
        with st.spinner("Working with GitHub and the AI model. This may take a little time…"):
            result = run_agent(repo_url.strip(), search_term.strip())
        st.session_state["last_result"] = result
    except ValueError as error:
        st.error(f"Invalid repository URL: {error}")
    except Exception as error:
        st.error(f"Agent run failed: {error}")
        st.caption(
            "Check your internet connection, GitHub API access, .env keys, "
            "and installed Python packages. Do not paste API keys into chat."
        )

result = st.session_state.get("last_result")
if result:
    repo_info = result["repository_data"].get("repository", {})
    st.divider()
    st.header(f"📦 {repo_info.get('name') or result['owner'] + '/' + result['repo']}")
    if repo_info.get("description"):
        st.write(repo_info["description"])

    metric1, metric2, metric3 = st.columns(3)
    metric1.metric("⭐ Stars", f"{repo_info.get('stars') or 0:,}")
    metric2.metric(
        "Open issues fetched",
        result["repository_data"].get("open_issue_count_returned", 0),
    )
    metric3.metric("Verified recommendations", len(result["verified_issues"]))

    if repo_info.get("url"):
        st.link_button("Open GitHub repository", repo_info["url"])

    st.subheader("🤖 AI Analysis")
    st.markdown(result["analysis"])

    st.subheader("✅ Verified open issues")
    st.caption(
        "These issues were present in the fetched issue data and then checked "
        "against GitHub. Open does not guarantee that an issue is unclaimed or "
        "that maintainers consider it beginner-friendly."
    )
    if result["verified_issues"]:
        for issue in result["verified_issues"]:
            with st.container(border=True):
                st.markdown(f"### #{issue['number']} — {issue.get('title') or 'Untitled issue'}")
                labels = issue.get("labels") or []
                st.write("**Labels:** " + (", ".join(labels) if labels else "None"))
                st.write(f"**Status:** {issue.get('state', 'unknown')}")
                st.link_button("View issue on GitHub", issue["url"])
    else:
        st.info(
            "No recommendations passed all verification checks. "
            "Try another repository or leave the code-search field blank."
        )

    if result["rejected_issues"]:
        with st.expander("Recommendations that did not pass verification"):
            for item in result["rejected_issues"]:
                st.write(f"Issue #{item['number']}: {item['reason']}")

    if result["search_term"]:
        with st.expander("Python code-search tool output"):
            for item in result["tool_results"]:
                if isinstance(item, dict) and (
                    "matches" in item or "search_term" in item or "files" in item
                ):
                    st.json(item)
