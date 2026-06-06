"""
github_utils.py — GitHub Pull Request Diff Fetcher.

Provides utilities to parse GitHub PR URLs, fetch diff data via PyGithub,
and format diffs into clean text for downstream LLM consumption.
"""

import os
import re
import logging
from typing import Optional

from github import Github, GithubException

logger = logging.getLogger(__name__)

# Maximum combined diff length sent to the LLM to stay within context limits.
_MAX_DIFF_CHARS = 15_000


# ---------------------------------------------------------------------------
# URL Parsing
# ---------------------------------------------------------------------------

def parse_pr_url(url: str) -> tuple[str, str, int]:
    """Extract owner, repo name, and PR number from a GitHub PR URL.

    Supports URLs with or without the ``https://`` scheme, and with or
    without a trailing slash.

    Args:
        url: A GitHub pull-request URL, e.g.
            ``https://github.com/owner/repo/pull/123``

    Returns:
        A 3-tuple of ``(owner, repo, pr_number)``.

    Raises:
        ValueError: If the URL does not match the expected pattern.

    Examples:
        >>> parse_pr_url("https://github.com/octocat/Hello-World/pull/42")
        ('octocat', 'Hello-World', 42)
    """
    pattern = r"(?:https?://)?github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    match = re.search(pattern, url.strip())

    if not match:
        raise ValueError(
            f"Invalid GitHub PR URL: '{url}'. "
            "Expected format: https://github.com/owner/repo/pull/123"
        )

    owner = match.group(1)
    repo = match.group(2)
    pr_number = int(match.group(3))

    logger.debug("Parsed PR URL → owner=%s, repo=%s, pr=#%d", owner, repo, pr_number)
    return owner, repo, pr_number


# ---------------------------------------------------------------------------
# PR Data Fetching
# ---------------------------------------------------------------------------

def fetch_pr_diff(owner: str, repo: str, pr_number: int) -> dict:
    """Fetch diff data for a GitHub Pull Request.

    Authenticates with ``GITHUB_TOKEN`` if available; falls back to
    unauthenticated access for public repositories (lower rate limits).

    Args:
        owner: Repository owner / organisation.
        repo: Repository name.
        pr_number: Pull request number.

    Returns:
        dict with keys:
            - title (str): PR title.
            - description (str): PR body / description.
            - author (str): GitHub login of the PR author.
            - files_changed (int): Number of files changed.
            - files (list[dict]): Per-file details (filename, status,
              patch, additions, deletions).
            - diff_text (str): Combined patch text across all files.

    Raises:
        ValueError: If the repository or PR cannot be found.
        RuntimeError: On GitHub API rate-limit or unexpected errors.
    """
    token = os.environ.get("GITHUB_TOKEN")
    gh = Github(token) if token else Github()

    try:
        repo_obj = gh.get_repo(f"{owner}/{repo}")
    except GithubException as exc:
        if exc.status == 404:
            raise ValueError(
                f"Repository '{owner}/{repo}' not found. "
                "Check the URL or ensure the repo is public."
            ) from exc
        if exc.status == 403:
            raise RuntimeError(
                "GitHub API rate limit exceeded. "
                "Set a GITHUB_TOKEN environment variable to increase limits."
            ) from exc
        raise RuntimeError(f"GitHub API error: {exc}") from exc

    try:
        pr = repo_obj.get_pull(pr_number)
    except GithubException as exc:
        if exc.status == 404:
            raise ValueError(
                f"Pull request #{pr_number} not found in '{owner}/{repo}'."
            ) from exc
        raise RuntimeError(f"GitHub API error fetching PR: {exc}") from exc

    logger.info(
        "Fetched PR #%d '%s' from %s/%s (%s)",
        pr_number,
        pr.title,
        owner,
        repo,
        pr.user.login,
    )

    files_list: list[dict] = []
    diff_parts: list[str] = []

    try:
        for f in pr.get_files():
            patch = f.patch or ""
            files_list.append(
                {
                    "filename": f.filename,
                    "status": f.status,
                    "patch": patch,
                    "additions": f.additions,
                    "deletions": f.deletions,
                }
            )
            if patch:
                diff_parts.append(f"--- {f.filename} ---\n{patch}")
    except GithubException as exc:
        logger.warning("Error iterating PR files: %s", exc)

    return {
        "title": pr.title,
        "description": pr.body or "",
        "author": pr.user.login,
        "files_changed": len(files_list),
        "files": files_list,
        "diff_text": "\n\n".join(diff_parts),
    }


# ---------------------------------------------------------------------------
# Diff Formatting
# ---------------------------------------------------------------------------

def format_diff_for_review(pr_data: dict) -> str:
    """Format PR data into a clean, LLM-friendly text block.

    Produces a structured string containing the PR title, author, file
    count, and the per-file patches.  If the total text exceeds
    ``_MAX_DIFF_CHARS``, it is truncated with a notice.

    Args:
        pr_data: A dict as returned by :func:`fetch_pr_diff`.

    Returns:
        str: Formatted review text ready for LLM consumption.
    """
    header = (
        f"PR: {pr_data.get('title', 'Untitled')}\n"
        f"Author: {pr_data.get('author', 'unknown')}\n"
        f"Files changed: {pr_data.get('files_changed', 0)}\n\n"
    )

    file_sections: list[str] = []
    for f in pr_data.get("files", []):
        patch = f.get("patch") or "(no diff available)"
        file_sections.append(f"--- {f['filename']} ---\n{patch}\n")

    body = "\n".join(file_sections)
    full_text = header + body

    if len(full_text) > _MAX_DIFF_CHARS:
        truncated = full_text[:_MAX_DIFF_CHARS]
        omitted = len(full_text) - _MAX_DIFF_CHARS
        truncated += f"\n... [truncated, {omitted:,} chars omitted]"
        logger.info(
            "Diff truncated from %d to %d chars.", len(full_text), _MAX_DIFF_CHARS
        )
        return truncated

    return full_text


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def fetch_pr_from_url(url: str) -> dict:
    """Parse a GitHub PR URL and fetch its diff data in one call.

    This is a convenience wrapper combining :func:`parse_pr_url` and
    :func:`fetch_pr_diff`.

    Args:
        url: A GitHub pull-request URL.

    Returns:
        dict: PR data as returned by :func:`fetch_pr_diff`.
    """
    owner, repo, pr_number = parse_pr_url(url)
    return fetch_pr_diff(owner, repo, pr_number)
