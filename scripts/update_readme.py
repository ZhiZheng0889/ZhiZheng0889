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


def gh_api(url: str, token: str | None):
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
    # include forks to reflect contributions to forked repos
    filtered = [r for r in repos if not r.get("archived")]
    # Sort by pushed_at desc
    filtered.sort(key=lambda r: r.get("pushed_at") or "", reverse=True)
    return filtered[:limit]


def fetch_recent_contributions(username: str, token: str | None, limit: int = 5) -> list[dict]:
    """Return repos from the user's most recent public events (includes forks)."""
    url = f"https://api.github.com/users/{username}/events/public?per_page=100"
    events = gh_api(url, token)
    if not isinstance(events, list):
        return []

    interesting = {
        "PushEvent",
        "PullRequestEvent",
        "IssuesEvent",
        "IssueCommentEvent",
        "PullRequestReviewEvent",
        "PullRequestReviewCommentEvent",
        "CreateEvent",
        "ReleaseEvent",
    }

    latest_by_repo: dict[str, str] = {}
    for ev in events:
        et = ev.get("type")
        if et not in interesting:
            continue
        repo = (ev.get("repo") or {}).get("name")  # owner/name
        if not repo:
            continue
        created = ev.get("created_at") or ""
        prev = latest_by_repo.get(repo)
        if not prev or created > prev:
            latest_by_repo[repo] = created

    # Sort repos by most recent event
    ordered = sorted(latest_by_repo.items(), key=lambda kv: kv[1], reverse=True)

    results: list[dict] = []
    for full_name, created in ordered[:limit]:
        api = f"https://api.github.com/repos/{full_name}"
        try:
            r = gh_api(api, token) or {}
        except Exception:
            r = {}
        r.setdefault("name", full_name.split("/")[-1])
        r.setdefault("full_name", full_name)
        r.setdefault("html_url", f"https://github.com/{full_name}")
        r.setdefault("description", "")
        r.setdefault("stargazers_count", 0)
        # use contribution time as the recency marker when pushed_at missing
        r.setdefault("pushed_at", created)
        results.append(r)
    return results


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
        parts = [f"- [{name}]({url}) - updated {pushed}"]
        if isinstance(stars, int) and stars > 0:
            parts.append(f"stars: {stars}")
        if desc:
            # limit description length for compactness
            short = desc if len(desc) <= 100 else desc[:97] + "..."
            parts.append(f"- {short}")
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
    # Prefer recent contributions (from Events API) to capture forks like 'gitpulse'.
    repos = fetch_recent_contributions(username, token, limit=5)
    if not repos:
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
