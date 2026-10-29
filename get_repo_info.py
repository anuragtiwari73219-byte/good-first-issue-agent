import requests


def get_repository_info(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}"

    response = requests.get(url, timeout=10)
    response.raise_for_status()

    data = response.json()

    return {
        "name": data["full_name"],
        "description": data["description"],
        "stars": data["stargazers_count"],
        "language": data["language"],
    }


try:
    info = get_repository_info("tiangolo", "fastapi")

    print("Repository:", info["name"])
    print("Description:", info["description"])
    print("Stars:", info["stars"])
    print("Language:", info["language"])

except requests.RequestException as error:
    print("GitHub API request failed:", error)