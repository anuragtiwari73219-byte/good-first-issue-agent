def calculate_issue_score(issue):
    """Calculate a transparent, rule-based beginner suitability score."""

    title = (issue.get("title") or "").strip()
    body = (issue.get("body") or "").strip()
    labels = {
        str(label).casefold()
        for label in issue.get("labels", [])
    }

    score = 0
    reasons = []
    warnings = []

    if title:
        score += 2
        reasons.append("Issue has a title.")
    else:
        warnings.append("Missing issue title.")

    if len(body) >= 100:
        score += 5
        reasons.append("Description provides useful context.")
    elif len(body) >= 30:
        score += 3
        reasons.append("Description provides some context.")
    else:
        warnings.append("Description is missing or too short.")

    if "good first issue" in labels:
        score += 5
        reasons.append("Has the good first issue label.")

    if "help wanted" in labels:
        score += 2
        reasons.append("Has the help wanted label.")

    if "documentation" in labels:
        score += 2
        reasons.append("May involve documentation work.")

    if "fixed" in labels or "duplicate" in labels or "wontfix" in labels:
        warnings.append("Potentially unsuitable status-related label.")
        score = max(0, score - 5)

    score = min(score, 16)

    if score >= 12:
        estimated_difficulty = "potentially beginner-friendly"
    elif score >= 7:
        estimated_difficulty = "needs further review"
    else:
        estimated_difficulty = "unclear or potentially difficult"

    return {
        "score": score,
        "maximum_score": 16,
        "estimated_difficulty": estimated_difficulty,
        "reasons": reasons,
        "warnings": warnings,
    }


if __name__ == "__main__":
    sample_issue = {
        "title": "Add a simple Python example",
        "body": "Add an example to the documentation showing how to use this feature.",
        "labels": ["good first issue", "documentation"],
    }

    result = calculate_issue_score(sample_issue)

    print("GOOD FIRST ISSUE SCORING TEST")
    print("=" * 40)
    print("Title:", sample_issue["title"])
    print("Score:", f'{result["score"]}/{result["maximum_score"]}')
    print("Estimated difficulty:", result["estimated_difficulty"])
    print("Reasons:", "; ".join(result["reasons"]))
    print("Warnings:", "; ".join(result["warnings"]) or "None")
