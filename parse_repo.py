from urllib.parse import urlparse


def parse_github_url(url):
    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")

    if parsed.hostname != "github.com":
        raise ValueError("Please enter a GitHub repository URL.")

    if len(parts) != 2 or not all(parts):
        raise ValueError("URL must look like owner/repo.")

    owner, repo = parts

    if repo.endswith(".git"):
        repo = repo[:-4]

    return owner, repo


url = input("Enter GitHub repository URL: ")

try:
    owner, repo = parse_github_url(url)
    print("Owner:", owner)
    print("Repository:", repo)

except ValueError as error:
    print("Error:", error)