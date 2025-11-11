import os
import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen


def get_username() -> str:
    repo = os.getenv("GITHUB_REPOSITORY", "")
    if "/" in repo:
        owner = repo.split("/", 1)[0]
        if owner:
            return owner
    actor = os.getenv("GITHUB_ACTOR")
    if actor:
        return actor
    # Fallback: set your username here if running locally
    return "zhizheng0889"


def gh_api(url: str, token: str | None) -> list[dict]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-readme-updater"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers)
    with urlopen(req) as resp:
        data = resp.read()
        return json.loads(data.decode("utf-8"))


def fetch_recent_repos(username: str, token: str | None, limit: int = 5) -> list[dict]:
    url = f"https://api.github.com/users/{username}/repos?per_page=100&type=owner&sort=pushed"
    repos = gh_api(url, token)
    # Filter noisy entries
    filtered = [
        r for r in repos
        if not r.get("fork") and not r.get("archived")
    ]
    # Sort by pushed_at desc
    filtered.sort(key=lambda r: r.get("pushed_at") or "", reverse=True)
    return filtered[:limit]


def fmt_date(iso_ts: str | None) -> str:
    if not iso_ts:
        return "unknown"
    dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d")


def build_markdown(repos: list[dict]) -> str:
    lines = []
    for r in repos:
        name = r.get("name", "repo")
        url = r.get("html_url", "")
        pushed = fmt_date(r.get("pushed_at"))
        stars = r.get("stargazers_count", 0)
        desc = (r.get("description") or "").strip()
        parts = [f"- [{name}]({url}) — updated {pushed}"]
        if isinstance(stars, int) and stars > 0:
            parts.append(f"⭐ {stars}")
        if desc:
            # limit description length for compactness
            short = desc if len(desc) <= 100 else desc[:97] + "..."
            parts.append(f"— {short}")
        lines.append(" ".join(parts))
    return "\n".join(lines) if lines else "- No recent activity found."


def replace_between_markers(content: str, marker_start: str, marker_end: str, new_block: str) -> str:
    start_idx = content.find(marker_start)
    end_idx = content.find(marker_end)
    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        # Append section if markers not found
        section = f"\n\n## Recent Activity\n\n{marker_start}\n{new_block}\n{marker_end}\n"
        return content.rstrip() + section
    start_idx_end = start_idx + len(marker_start)
    return content[:start_idx_end] + "\n" + new_block + "\n" + content[end_idx:]


def main():
    username = get_username()
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    repos = fetch_recent_repos(username, token, limit=5)
    md = build_markdown(repos)

    readme_path = os.path.join(os.getcwd(), "README.md")
    with open(readme_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    updated = replace_between_markers(
        content,
        marker_start="<!--RECENT_REPOS:START-->",
        marker_end="<!--RECENT_REPOS:END-->",
        new_block=md,
    )

    if updated != content:
        with open(readme_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(updated)


if __name__ == "__main__":
    main()

