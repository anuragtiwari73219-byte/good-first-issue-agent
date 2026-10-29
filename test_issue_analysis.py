import json
import os

from dotenv import load_dotenv
from google import genai

from agent import MODEL
from issue_scoring import calculate_issue_score
from test_issue_details import get_issue_details


def analyze_issue_with_ai(issue):
    """Assess issue difficulty using evidence from its description."""

    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY was not found in .env")

    client = genai.Client(api_key=api_key)

    issue_data = {
        "title": issue.get("title"),
        "body": issue.get("body"),
        "labels": issue.get("labels", []),
        "url": issue.get("url"),
        "state": issue.get("state"),
    }

    prompt = """
You are assessing a real GitHub issue for a beginner contributor.

Use only the supplied issue data. You have not inspected the repository.

Rules:
- A good-first-issue label does not prove the task is easy.
- Consider the number of interfaces and components mentioned.
- Consider investigation, implementation, and testing effort.
- A shared utility could reduce complexity, but do not assume one exists.
- Do not claim that possible work is confirmed work.
- If important information is missing, use uncertain where appropriate.
- Support the difficulty assessment with specific evidence.
- Do not invent files, functions, or implementation details.

Return only valid JSON with exactly these keys:
{
  "task_summary": "Short summary",
  "difficulty": "beginner, intermediate, advanced, or uncertain",
  "difficulty_reasons": ["Evidence-based reasons"],
  "confidence": "low, medium, or high",
  "scope": "focused, moderate, broad, or uncertain",
  "affected_components": ["Components mentioned in the issue"],
  "codebase_inspection_required": true,
  "task_clarity": "clear, partly clear, unclear, or uncertain",
  "skills_needed": ["Relevant skills"],
  "likely_work": ["Explicitly stated work or clearly marked inferences"],
  "testing_effort": "low, medium, high, or uncertain",
  "blockers": ["Known or possible blockers"],
  "evidence": ["Specific evidence from the issue"],
  "unknowns": ["Details requiring investigation"],
  "first_steps": ["Practical investigation steps"]
}

Important:
- codebase_inspection_required must be true or false, not a string.
- Assess the actual scope, not just the issue labels.
- Do not automatically classify an issue as beginner-friendly.
- If the description mentions several interfaces, explain how that affects
  the estimated scope without assuming each needs a separate code change.

Issue data:
""" + json.dumps(issue_data, ensure_ascii=False)

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
    )

    if not response.text:
        raise RuntimeError("The AI returned an empty response.")

    text = response.text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    result = json.loads(text)

    required_keys = {
        "task_summary",
        "difficulty",
        "difficulty_reasons",
        "confidence",
        "scope",
        "affected_components",
        "codebase_inspection_required",
        "task_clarity",
        "skills_needed",
        "likely_work",
        "testing_effort",
        "blockers",
        "evidence",
        "unknowns",
        "first_steps",
    }

    if not isinstance(result, dict) or set(result.keys()) != required_keys:
        raise ValueError("AI response did not match the required JSON structure.")

    allowed_values = {
        "difficulty": {"beginner", "intermediate", "advanced", "uncertain"},
        "confidence": {"low", "medium", "high"},
        "scope": {"focused", "moderate", "broad", "uncertain"},
        "task_clarity": {"clear", "partly clear", "unclear", "uncertain"},
        "testing_effort": {"low", "medium", "high", "uncertain"},
    }

    for field, allowed in allowed_values.items():
        if not isinstance(result[field], str) or result[field] not in allowed:
            raise ValueError(f"Invalid value returned for {field}.")

    if not isinstance(result["codebase_inspection_required"], bool):
        raise ValueError("codebase_inspection_required must be true or false.")

    list_fields = {
        "difficulty_reasons",
        "affected_components",
        "skills_needed",
        "likely_work",
        "blockers",
        "evidence",
        "unknowns",
        "first_steps",
    }

    for field in list_fields:
        if not isinstance(result[field], list) or not all(
            isinstance(item, str) for item in result[field]
        ):
            raise ValueError(f"{field} must be a list of strings.")

    if not isinstance(result["task_summary"], str):
        raise ValueError("task_summary must be a string.")

    return result


def main():
    repository = input(
        "Enter repository (owner/repo), for example pyrite-wiki/pyrite: "
    ).strip()

    issue_number_text = input("Enter issue number: ").strip()

    if repository.count("/") != 1:
        print("Invalid repository. Use owner/repo format.")
        return 1

    owner, repo = repository.split("/", 1)

    if not issue_number_text.isdigit() or int(issue_number_text) <= 0:
        print("Issue number must be a positive integer.")
        return 1

    issue_number = int(issue_number_text)

    print("\nFetching the real GitHub issue...")

    try:
        issue = get_issue_details(repository, issue_number)

        if not issue:
            print("This item is a pull request, not a regular issue.")
            return 1

        if issue.get("state") != "open":
            print("This issue is not currently open. State:", issue.get("state"))
            return 1

        print("Issue fetched:", issue.get("title"))

        print("\nCalculating the rule-based score...")
        score = calculate_issue_score(issue)

        print(f"Rule-based score: {score['score']}/{score['maximum_score']}")
        print("Rule-based assessment:", score["estimated_difficulty"])

        print("\nAsking AI to analyze the issue...")
        analysis = analyze_issue_with_ai(issue)

        print("\n" + "=" * 60)
        print("AI ISSUE ANALYSIS")
        print("=" * 60)
        print(json.dumps(analysis, indent=2, ensure_ascii=False))

        print("\n" + "=" * 60)
        print("COMPARISON")
        print("=" * 60)
        print("Rule-based assessment:", score["estimated_difficulty"])
        print("AI assessment:", analysis["difficulty"])
        print("AI estimated scope:", analysis["scope"])
        print("AI confidence:", analysis["confidence"])
        print(
            "\nNote: These are estimates based on the issue description. "
            "The actual code and tests still need inspection."
        )

    except Exception as error:
        print("\nIssue analysis failed.")
        print("Error type:", type(error).__name__)
        print("Details:", str(error))
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
