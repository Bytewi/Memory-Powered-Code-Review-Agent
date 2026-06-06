"""
memory.py — Hindsight SDK Wrapper for the Memory-Powered Code Review Agent.

This module is the CORE of the entire project. Every interaction with Hindsight's
persistent memory layer goes through these functions:
  - recall_developer_context: Retrieve a developer's past coding history
  - reflect_on_developer: Generate a synthesized developer profile
  - retain_review_session: Store a new review session into long-term memory
  - get_review_count: Count how many reviews exist for a developer

All retain/recall/reflect calls are prominently marked for demo visibility.
"""

import os
import json
import logging
import re
from datetime import datetime
from typing import Optional

from hindsight_client import Hindsight
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Client Initialization
# ---------------------------------------------------------------------------

def init_hindsight() -> Hindsight:
    """Initialize and return a configured Hindsight client.

    Loads environment variables from ``.env`` and creates a
    :class:`Hindsight` client using ``HINDSIGHT_SERVER_URL`` (with a
    sensible default) and ``HINDSIGHT_API_KEY``.

    Returns:
        Hindsight: A ready-to-use Hindsight client instance.

    Raises:
        ValueError: If ``HINDSIGHT_API_KEY`` is not set.
    """
    load_dotenv()

    base_url = os.environ.get(
        "HINDSIGHT_SERVER_URL",
        "https://api.hindsight.vectorize.io",
    )
    api_key = os.environ.get("HINDSIGHT_API_KEY")

    if not api_key:
        raise ValueError(
            "HINDSIGHT_API_KEY environment variable is not set. "
            "Please add it to your .env file."
        )

    client = Hindsight(base_url=base_url, api_key=api_key)
    logger.info("Hindsight client initialized (server: %s)", base_url)
    return client


# ---------------------------------------------------------------------------
# RECALL — Retrieve Developer Context
# ---------------------------------------------------------------------------

def recall_developer_context(
    client: Hindsight,
    developer_id: str,
    language: str = "",
    repo: str = "",
) -> dict:
    """Recall a developer's coding history from Hindsight memory.

    Queries the developer's memory bank for past coding issues, patterns,
    and fixes.  The results are parsed into a structured dictionary that
    downstream consumers (the LLM prompt builder, the Streamlit sidebar,
    etc.) can use directly.

    Args:
        client: An initialised Hindsight client.
        developer_id: Unique identifier (bank_id) for the developer.
        language: Optional programming language filter.
        repo: Optional repository filter.

    Returns:
        dict with keys:
            - review_count (int): Number of distinct past reviews found.
            - recurring_issues (list[str]): Issues that appear across
              multiple reviews.
            - resolved_issues (list[str]): Issues explicitly marked as
              fixed / resolved.
            - raw_memories (list[str]): Raw text from each memory result.
    """

    # ====================================================================
    # ======  HINDSIGHT RECALL — Retrieving developer's coding history  ======
    # ====================================================================

    defaults: dict = {
        "review_count": 0,
        "recurring_issues": [],
        "resolved_issues": [],
        "raw_memories": [],
    }

    try:
        tags = [language, "code-review"] if language else ["code-review"]

        logger.info(
            "Recalling developer context for '%s' (language=%s, repo=%s)",
            developer_id,
            language or "<any>",
            repo or "<any>",
        )

        results = client.recall(
            bank_id=developer_id,
            query=(
                f"What coding issues, patterns, and mistakes does this "
                f"developer make in {language}? What issues have they fixed?"
            ),
            tags=tags,
            tags_match="any",
            budget="high",
            max_tokens=2048,
        )

        if not results or not getattr(results, "results", None):
            logger.info("No memories found for developer '%s'.", developer_id)
            return defaults

        # --- Parse results ---------------------------------------------------

        raw_memories: list[str] = []
        review_numbers: set[str] = set()
        issue_counts: dict[str, int] = {}
        resolved_issues: list[str] = []

        for result in results.results:
            text: str = getattr(result, "text", "") or ""
            raw_memories.append(text)

            # Extract review_number from metadata if available
            metadata = getattr(result, "metadata", {}) or {}
            rn = metadata.get("review_number")
            if rn is not None:
                review_numbers.add(str(rn))

            # Detect recurring issues — look for common issue-type keywords
            lower_text = text.lower()
            issue_keywords = [
                "missing error handling",
                "no type hints",
                "unused import",
                "magic number",
                "hardcoded",
                "no docstring",
                "naming convention",
                "security",
                "sql injection",
                "race condition",
                "memory leak",
                "complexity",
                "duplicate code",
                "no validation",
                "missing test",
                "bare except",
                "global variable",
            ]
            for keyword in issue_keywords:
                if keyword in lower_text:
                    issue_counts[keyword] = issue_counts.get(keyword, 0) + 1

            # Detect resolved issues
            resolved_patterns = [
                r"fixed[:\s]+(.*?)(?:\.|$)",
                r"resolved[:\s]+(.*?)(?:\.|$)",
                r"addressed[:\s]+(.*?)(?:\.|$)",
                r"improvement[:\s]+(.*?)(?:\.|$)",
            ]
            for pattern in resolved_patterns:
                matches = re.findall(pattern, lower_text, re.IGNORECASE)
                resolved_issues.extend(
                    m.strip().capitalize() for m in matches if m.strip()
                )

        # Issues appearing in 2+ results are considered recurring
        recurring = [
            issue.replace("_", " ").title()
            for issue, count in issue_counts.items()
            if count >= 2
        ]

        context = {
            "review_count": len(review_numbers),
            "recurring_issues": recurring,
            "resolved_issues": list(dict.fromkeys(resolved_issues)),  # dedupe
            "raw_memories": raw_memories,
        }

        logger.info(
            "Recalled %d memories across %d reviews for '%s'.",
            len(raw_memories),
            context["review_count"],
            developer_id,
        )
        return context

    except Exception as exc:
        logger.error(
            "Error recalling developer context for '%s': %s",
            developer_id,
            exc,
            exc_info=True,
        )
        return defaults


# ---------------------------------------------------------------------------
# REFLECT — Synthesize Developer Profile
# ---------------------------------------------------------------------------

def reflect_on_developer(client: Hindsight, developer_id: str) -> str:
    """Generate a synthesized profile of a developer via Hindsight reflect.

    This asks Hindsight to summarize all stored memories for the given
    developer into a concise, human-readable narrative about their coding
    style, recurring mistakes, and growth trajectory.

    Args:
        client: An initialised Hindsight client.
        developer_id: Unique identifier (bank_id) for the developer.

    Returns:
        str: A narrative summary of the developer's profile, or a
        fallback message if no data is available.
    """

    # ====================================================================
    # ======  HINDSIGHT REFLECT — Generating synthesized developer profile  ======
    # ====================================================================

    fallback = (
        "No developer profile available yet. "
        "Submit a code review to start building one."
    )

    try:
        logger.info("Reflecting on developer '%s'…", developer_id)

        response = client.reflect(
            bank_id=developer_id,
            query=(
                "Summarize this developer's coding style, recurring mistakes, "
                "improvements over time, and current skill level. "
                "Be specific about patterns you've observed."
            ),
            budget="mid",
            max_tokens=1024,
        )

        text = getattr(response, "text", None) or getattr(response, "result", None)

        if not text:
            logger.info("Reflect returned empty for developer '%s'.", developer_id)
            return fallback

        logger.info("Reflect profile generated for '%s' (%d chars).", developer_id, len(str(text)))
        return str(text)

    except Exception as exc:
        logger.error(
            "Error reflecting on developer '%s': %s",
            developer_id,
            exc,
            exc_info=True,
        )
        return fallback


# ---------------------------------------------------------------------------
# RETAIN — Store a Review Session
# ---------------------------------------------------------------------------

def retain_review_session(
    client: Hindsight,
    developer_id: str,
    language: str,
    repo: str,
    issues_found: list[dict],
    review_number: int,
) -> bool:
    """Persist a completed code-review session into Hindsight memory.

    Builds a human-readable content string summarizing the review and
    stores it with structured metadata and tags so it can be recalled
    and reflected upon later.

    Args:
        client: An initialised Hindsight client.
        developer_id: Unique identifier (bank_id) for the developer.
        language: Programming language of the reviewed code.
        repo: Repository name or identifier.
        issues_found: List of issue dicts, each with keys ``severity``,
            ``type``, and ``description``.
        review_number: Monotonically increasing review counter.

    Returns:
        bool: ``True`` if the session was retained successfully,
        ``False`` otherwise.
    """

    # ====================================================================
    # ======  HINDSIGHT RETAIN — Storing this review session into persistent memory  ======
    # ====================================================================

    try:
        # --- Build content string -----------------------------------------
        lines: list[str] = [
            f"Code Review Session #{review_number}",
            f"Language: {language}",
            f"Repository: {repo}",
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Total Issues Found: {len(issues_found)}",
            "",
            "Issues:",
            "-" * 40,
        ]

        severity_counts: dict[str, int] = {}
        for idx, issue in enumerate(issues_found, start=1):
            severity = issue.get("severity", "unknown").upper()
            issue_type = issue.get("type", "general")
            description = issue.get("description", "No description provided.")

            severity_counts[severity] = severity_counts.get(severity, 0) + 1

            lines.append(
                f"  {idx}. [{severity}] {issue_type}: {description}"
            )

        lines.append("")
        lines.append("Summary:")
        summary_parts = [
            f"{count} {sev.lower()}" for sev, count in severity_counts.items()
        ]
        lines.append(f"  {', '.join(summary_parts) or 'No issues'}")

        content_string = "\n".join(lines)

        logger.info(
            "Retaining review #%d for developer '%s' (%d issues).",
            review_number,
            developer_id,
            len(issues_found),
        )

        client.retain(
            bank_id=developer_id,
            content=content_string,
            context="code-review-session",
            document_id=f"review-{developer_id}-{review_number}",
            tags=[language, repo, "code-review"],
            metadata={
                "review_number": str(review_number),
                "repo": repo,
                "language": language,
                "timestamp": datetime.now().isoformat(),
            },
        )

        logger.info(
            "Successfully retained review #%d for '%s'.",
            review_number,
            developer_id,
        )
        return True

    except Exception as exc:
        logger.error(
            "Error retaining review #%d for '%s': %s",
            review_number,
            developer_id,
            exc,
            exc_info=True,
        )
        return False


# ---------------------------------------------------------------------------
# Helper — Get Review Count
# ---------------------------------------------------------------------------

def get_review_count(client: Hindsight, developer_id: str) -> int:
    """Return the number of past reviews stored for a developer.

    Performs a lightweight recall query and inspects ``review_number``
    metadata to find the highest value seen, which acts as a count.

    Args:
        client: An initialised Hindsight client.
        developer_id: Unique identifier (bank_id) for the developer.

    Returns:
        int: The highest review number found, or ``0`` if none exist.
    """

    # ====================================================================
    # ======  HINDSIGHT RECALL — Counting past reviews for developer  ======
    # ====================================================================

    try:
        results = client.recall(
            bank_id=developer_id,
            query="How many code reviews has this developer had?",
            tags=["code-review"],
            tags_match="any",
            budget="low",
            max_tokens=512,
        )

        if not results or not getattr(results, "results", None):
            return 0

        max_review = 0
        for result in results.results:
            metadata = getattr(result, "metadata", {}) or {}
            rn = metadata.get("review_number")
            if rn is not None:
                try:
                    max_review = max(max_review, int(rn))
                except (ValueError, TypeError):
                    pass

        logger.info(
            "Developer '%s' has %d past review(s).",
            developer_id,
            max_review,
        )
        return max_review

    except Exception as exc:
        logger.error(
            "Error getting review count for '%s': %s",
            developer_id,
            exc,
            exc_info=True,
        )
        return 0
