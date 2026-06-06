"""
utils.py — Shared Text Formatting Utilities.

Provides helper functions for parsing LLM review output, truncating
diffs, detecting programming languages from file extensions, and
formatting memory context for the Streamlit sidebar.
"""

import re
import logging
from collections import Counter
from typing import Optional

logger = logging.getLogger(__name__)

# File extension → language mapping
_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".c": "c",
    ".cs": "csharp",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".r": "r",
    ".R": "r",
    ".sh": "bash",
    ".bash": "bash",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".json": "json",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".vue": "vue",
    ".dart": "dart",
    ".lua": "lua",
    ".pl": "perl",
    ".ex": "elixir",
    ".exs": "elixir",
}


# ---------------------------------------------------------------------------
# LLM Output Parsing
# ---------------------------------------------------------------------------

def parse_review_sections(raw_text: str) -> dict:
    """Parse LLM review output into categorised issue sections.

    Scans the raw text for severity markers (emoji or keywords) and
    groups each flagged issue into ``critical``, ``style``, or
    ``suggestions`` buckets.

    Recognised section headers:
        - ``🔴`` or ``CRITICAL`` → critical issues
        - ``🟡`` or ``STYLE``    → style issues
        - ``🟢`` or ``SUGGESTION`` → suggestions

    Within each section, lines starting with ``-`` are treated as
    individual issues. Multi-line continuations (indented lines) are
    appended to the previous issue.

    Args:
        raw_text: Raw text output from the review LLM.

    Returns:
        dict with keys ``"critical"``, ``"style"``, and
        ``"suggestions"``, each mapping to a ``list[str]`` of issue
        descriptions (one string per issue).
    """
    sections: dict[str, list[str]] = {
        "critical": [],
        "style": [],
        "suggestions": [],
    }

    if not raw_text:
        return sections

    lines = raw_text.split("\n")
    current_section: Optional[str] = None
    current_issue_lines: list[str] = []

    def _flush_issue() -> None:
        """Flush the current accumulated issue into the active section."""
        nonlocal current_issue_lines
        if current_section and current_issue_lines:
            issue_text = " ".join(current_issue_lines).strip()
            # Strip leading bullet characters
            issue_text = re.sub(r"^[-•*]\s*", "", issue_text)
            if issue_text and issue_text.lower() not in ("no issues found.", "no issues found"):
                sections[current_section].append(issue_text)
        current_issue_lines = []

    for line in lines:
        stripped = line.strip()

        # ── Section header detection ──────────────────────────────────────
        is_critical = "🔴" in stripped or re.search(
            r"\b(CRITICAL\s*ISSUES?|CRITICAL)\b", stripped, re.IGNORECASE
        )
        is_style = "🟡" in stripped or re.search(
            r"\b(STYLE\s*&?\s*STANDARDS?|STYLE)\b", stripped, re.IGNORECASE
        )
        is_suggestion = "🟢" in stripped or re.search(
            r"\b(SUGGESTIONS?|IMPROVEMENTS?|OPTIMISATIONS?)\b",
            stripped,
            re.IGNORECASE,
        )

        if is_critical and not (is_style or is_suggestion):
            _flush_issue()
            current_section = "critical"
            current_issue_lines = []
            continue

        if is_style and not (is_critical or is_suggestion):
            _flush_issue()
            current_section = "style"
            current_issue_lines = []
            continue

        if is_suggestion and not (is_critical or is_style):
            _flush_issue()
            current_section = "suggestions"
            current_issue_lines = []
            continue

        # ── Issue line detection (within an active section) ───────────────
        if current_section is None or not stripped:
            continue

        is_new_bullet = stripped.startswith(("-", "•", "*")) and len(stripped) > 2

        if is_new_bullet:
            # Start a new individual issue
            _flush_issue()
            current_issue_lines = [stripped]
        else:
            # Continuation / sub-detail of current issue
            current_issue_lines.append(stripped)

    # Flush the last issue
    _flush_issue()

    logger.debug(
        "Parsed review sections: %d critical, %d style, %d suggestions.",
        len(sections["critical"]),
        len(sections["style"]),
        len(sections["suggestions"]),
    )
    return sections


# ---------------------------------------------------------------------------
# Issue Counting
# ---------------------------------------------------------------------------

def format_issue_count(sections: dict) -> str:
    """Return a one-line summary of issue counts by category.

    Args:
        sections: A dict as returned by :func:`parse_review_sections`.

    Returns:
        str: e.g. ``"2 critical, 3 style, 1 suggestion"``
    """
    parts: list[str] = []

    critical = len(sections.get("critical", []))
    style = len(sections.get("style", []))
    suggestions = len(sections.get("suggestions", []))

    if critical:
        parts.append(f"{critical} critical")
    if style:
        parts.append(f"{style} style")
    if suggestions:
        parts.append(f"{suggestions} suggestion{'s' if suggestions != 1 else ''}")

    return ", ".join(parts) if parts else "No issues found"


# ---------------------------------------------------------------------------
# Diff Truncation
# ---------------------------------------------------------------------------

def truncate_diff(diff_text: str, max_chars: int = 12_000) -> str:
    """Truncate a diff string if it exceeds *max_chars*.

    When truncation occurs, a notice is appended indicating how many
    characters were omitted.

    Args:
        diff_text: The raw diff text.
        max_chars: Maximum number of characters to retain.

    Returns:
        str: The (possibly truncated) diff text.
    """
    if not diff_text or len(diff_text) <= max_chars:
        return diff_text

    remaining = len(diff_text) - max_chars
    truncated = diff_text[:max_chars]
    truncated += f"\n... [truncated, {remaining:,} chars omitted]"
    logger.info(
        "Diff truncated from %d to %d chars (%d omitted).",
        len(diff_text),
        max_chars,
        remaining,
    )
    return truncated


# ---------------------------------------------------------------------------
# Language Detection
# ---------------------------------------------------------------------------

def extract_language_from_diff(diff_text: str) -> str:
    """Detect the dominant programming language from a unified diff.

    Inspects lines starting with ``---`` or ``+++`` (the file-header
    lines in unified diffs) and extracts file extensions.  The most
    frequently occurring language wins.

    Args:
        diff_text: Unified diff text (e.g. from ``git diff`` or a
            GitHub patch).

    Returns:
        str: Lowercase language name (e.g. ``"python"``). Defaults to
        ``"python"`` if no extensions are detected.
    """
    if not diff_text:
        return "python"

    extensions_found: list[str] = []

    # Match file paths in diff header lines and in "--- filename ---" format
    patterns = [
        r"^(?:---|\+\+\+)\s+[ab]?/?(.+?)(?:\s|$)",  # standard unified diff
        r"^---\s+(.+?)\s+---",                        # custom "--- file ---" format
    ]

    for line in diff_text.split("\n"):
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                filepath = match.group(1).strip()
                # Extract extension
                dot_idx = filepath.rfind(".")
                if dot_idx != -1:
                    ext = filepath[dot_idx:].lower()
                    if ext in _EXTENSION_MAP:
                        extensions_found.append(ext)
                break  # one match per line is enough

    if not extensions_found:
        logger.debug("No recognised file extensions in diff; defaulting to 'python'.")
        return "python"

    # Pick the most common language
    lang_counts = Counter(_EXTENSION_MAP[ext] for ext in extensions_found)
    dominant_language = lang_counts.most_common(1)[0][0]

    logger.debug(
        "Detected languages: %s → dominant: %s",
        dict(lang_counts),
        dominant_language,
    )
    return dominant_language


# ---------------------------------------------------------------------------
# Memory Display Formatting
# ---------------------------------------------------------------------------

def format_memory_for_display(memory_context: dict) -> dict:
    """Format recalled memory context for the Streamlit sidebar.

    Takes the raw dict returned by
    :func:`app.memory.recall_developer_context` and reshapes it into a
    display-friendly structure.

    Args:
        memory_context: Dict with ``review_count``, ``recurring_issues``,
            ``resolved_issues``, and ``raw_memories`` keys.

    Returns:
        dict with keys:
            - review_count (int): Total reviews found.
            - top_issues (list[str]): Up to 5 most important recurring
              issues.
            - resolved (list[str]): Up to 5 resolved issues.
            - summary (str): A short prose summary for the sidebar.
    """
    review_count = memory_context.get("review_count", 0)
    recurring = memory_context.get("recurring_issues", [])
    resolved = memory_context.get("resolved_issues", [])
    raw = memory_context.get("raw_memories", [])

    # Build a concise summary
    if review_count == 0:
        summary = "🆕 New developer — no prior review history."
    elif review_count < 3:
        summary = (
            f"📝 Early history — {review_count} review(s) on record. "
            "Patterns are still emerging."
        )
    else:
        issue_note = (
            f" Known recurring issues: {', '.join(recurring[:3])}."
            if recurring
            else ""
        )
        resolved_note = (
            f" Recently resolved: {', '.join(resolved[:2])}."
            if resolved
            else ""
        )
        summary = (
            f"📊 {review_count} reviews on record.{issue_note}{resolved_note}"
        )

    return {
        "review_count": review_count,
        "top_issues": recurring[:5],
        "resolved": resolved[:5],
        "summary": summary,
    }
