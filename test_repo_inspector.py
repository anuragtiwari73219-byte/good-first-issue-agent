from repo_inspector import search_repository_code

result = search_repository_code(
    "pyrite-wiki",
    "pyrite",
    "filter_updated_since",
    max_files=100,
)

print("Repository:", result["repository"])
print("Files checked:", result["files_checked"])
print("Matches:", len(result["matches"]))

for match in result["matches"][:10]:
    print(
        "{}:{} - {}".format(
            match["path"],
            match["line"],
            match["text"],
        )
    )