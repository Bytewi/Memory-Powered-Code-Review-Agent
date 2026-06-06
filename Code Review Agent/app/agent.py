"""
agent.py — Code Review Agent Logic.

This module is the brain of the review agent. It:
  1. Recalls the developer's history from Hindsight memory
  2. Constructs prompts that incorporate past context
  3. Sends the diff + memory to Groq (qwen/qwen3-32b) for review
  4. Parses the structured review output
  5. Stores the new review session back into Hindsight memory

The key insight: reviews are NOT stateless. Memory makes each review
smarter than the last.
"""

import os
import logging
import time
from typing import Optional

from groq import Groq
from dotenv import load_dotenv

from app.memory import (
    init_hindsight,
    recall_developer_context,
    retain_review_session,
    get_review_count,
)
from app.utils import parse_review_sections, truncate_diff, extract_language_from_diff

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Groq Client Initialization
# ---------------------------------------------------------------------------

GROQ_MODEL = "qwen/qwen3-32b"
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


def init_groq() -> Groq:
    """Initialize and return a configured Groq client.

    Returns:
        Groq: A ready-to-use Groq client instance.

    Raises:
        ValueError: If ``GROQ_API_KEY`` is not set.
    """
    load_dotenv()

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY environment variable is not set. "
            "Please add it to your .env file."
        )

    client = Groq(api_key=api_key)
    logger.info("Groq client initialized (model: %s)", GROQ_MODEL)
    return client


# ---------------------------------------------------------------------------
# Prompt Construction
# ---------------------------------------------------------------------------

def build_system_prompt(memory_context: dict) -> str:
    """Build the system prompt, injecting developer memory when available.

    If we have memory of this developer, the prompt includes their history
    so the LLM can personalize its feedback.

    Args:
        memory_context: Dict from recall_developer_context() with keys
            review_count, recurring_issues, resolved_issues, raw_memories.

    Returns:
        str: The full system prompt.
    """
    base_prompt = """You are an expert code reviewer with years of experience across multiple languages and frameworks. You provide thorough, actionable code reviews.

REVIEW FORMAT — You MUST structure your output EXACTLY like this:

🔴 CRITICAL ISSUES (bugs, security vulnerabilities, data loss risks)
- [file:line] **Issue title**: Description of what's wrong → How to fix it

🟡 STYLE & STANDARDS (naming, formatting, best practices)
- [file:line] **Issue title**: Description of what's wrong → How to fix it

🟢 SUGGESTIONS (improvements, optimizations, refactoring ideas)
- [file:line] **Issue title**: Description of what's wrong → How to fix it

RULES:
- Every issue MUST include the file name and line reference
- Every issue MUST have a concrete fix suggestion
- If a section has no issues, write "No issues found." under it
- Be specific, not vague. Reference actual code from the diff.
- Keep the tone professional but constructive"""

    # Inject memory context if available
    review_count = memory_context.get("review_count", 0)
    recurring = memory_context.get("recurring_issues", [])
    resolved = memory_context.get("resolved_issues", [])
    raw = memory_context.get("raw_memories", [])

    if review_count > 0:
        memory_section = f"""

DEVELOPER MEMORY — You have reviewed this developer's code {review_count} time(s) before.
Use this context to personalize your review:"""

        if recurring:
            memory_section += f"""

RECURRING PATTERNS (flag these more firmly if they appear again):
{chr(10).join(f'  • {issue}' for issue in recurring[:5])}"""

        if resolved:
            memory_section += f"""

RECENTLY RESOLVED (acknowledge positively if these are no longer present):
{chr(10).join(f'  ✅ {issue}' for issue in resolved[:5])}"""

        if raw:
            memory_section += f"""

PAST REVIEW NOTES:
{chr(10).join(f'  — {mem[:200]}' for mem in raw[:3])}"""

        memory_section += """

PERSONALIZATION GUIDELINES:
- If you see a recurring issue AGAIN, call it out firmly: "This pattern has appeared in previous reviews..."
- If a previously recurring issue is now FIXED, acknowledge it: "Great improvement — this issue from past reviews has been addressed."
- Adjust your tone based on review count: more collegial for experienced developers, more educational for newer ones.
- Reference specific past patterns when relevant."""

        base_prompt += memory_section

    return base_prompt


def build_review_prompt(diff_text: str, memory_context: dict) -> str:
    """Build the user prompt containing the code diff and review instructions.

    Args:
        diff_text: The code diff to review.
        memory_context: Dict from recall_developer_context().

    Returns:
        str: The user-facing prompt.
    """
    review_count = memory_context.get("review_count", 0)

    prefix = ""
    if review_count > 0:
        prefix = f"This is review #{review_count + 1} for this developer. "

    prompt = f"""{prefix}Please review the following code changes:

```diff
{diff_text}
```

Provide your review following the exact format specified (🔴 Critical, 🟡 Style, 🟢 Suggestions).
Be thorough but concise. Every issue must reference a specific file and line."""

    return prompt


# ---------------------------------------------------------------------------
# Groq LLM Call
# ---------------------------------------------------------------------------

def call_groq(
    groq_client: Groq,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.6,
    max_tokens: int = 4096,
) -> str:
    """Call the Groq API with retry logic for rate limiting.

    Args:
        groq_client: An initialised Groq client.
        system_prompt: The system message.
        user_prompt: The user message containing the diff.
        temperature: Sampling temperature (0.0 to 2.0).
        max_tokens: Maximum tokens in the response.

    Returns:
        str: The LLM's response text.

    Raises:
        Exception: If all retries are exhausted.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "Calling Groq API (model=%s, attempt=%d/%d)",
                GROQ_MODEL,
                attempt,
                MAX_RETRIES,
            )

            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            content = response.choices[0].message.content
            logger.info(
                "Groq response received (%d chars).",
                len(content) if content else 0,
            )
            return content or ""

        except Exception as exc:
            error_str = str(exc).lower()
            if "429" in error_str or "rate" in error_str:
                wait = RETRY_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "Rate limited by Groq. Retrying in %ds (attempt %d/%d).",
                    wait,
                    attempt,
                    MAX_RETRIES,
                )
                time.sleep(wait)
            else:
                logger.error("Groq API error: %s", exc, exc_info=True)
                if attempt == MAX_RETRIES:
                    raise
                time.sleep(RETRY_DELAY)

    raise RuntimeError("Groq API call failed after all retries.")


# ---------------------------------------------------------------------------
# Main Review Orchestrator
# ---------------------------------------------------------------------------

def run_review(
    diff_text: str,
    developer_id: str,
    language: str = "",
    repo: str = "",
    groq_client: Optional[Groq] = None,
    hindsight_client=None,
) -> dict:
    """Run a full code review: recall → prompt → LLM → parse → retain.

    This is the main entry point for the review pipeline. It:
    1. Recalls the developer's history from Hindsight memory
    2. Builds memory-aware prompts
    3. Calls Groq for the review
    4. Parses the response into structured sections
    5. Stores the review into Hindsight memory for next time

    Args:
        diff_text: The code diff to review.
        developer_id: Developer's unique ID (used as bank_id).
        language: Programming language (auto-detected if empty).
        repo: Repository identifier.
        groq_client: Pre-initialised Groq client (created if None).
        hindsight_client: Pre-initialised Hindsight client (created if None).

    Returns:
        dict with keys:
            - review_text (str): Full formatted review from the LLM.
            - sections (dict): Parsed review sections.
            - memory_context (dict): The recalled memory used.
            - review_number (int): This review's sequence number.
            - issues_found (list[dict]): Structured list of issues.
    """
    # --- Initialise clients if needed ---
    if hindsight_client is None:
        hindsight_client = init_hindsight()
    if groq_client is None:
        groq_client = init_groq()

    # --- Auto-detect language ---
    if not language:
        language = extract_language_from_diff(diff_text)
        logger.info("Auto-detected language: %s", language)

    # --- Truncate oversized diffs ---
    diff_text = truncate_diff(diff_text, max_chars=12000)

    # ===================================================================
    # STEP 1 — RECALL: Retrieve developer's history from Hindsight memory
    # ===================================================================
    memory_context = recall_developer_context(
        hindsight_client, developer_id, language, repo
    )

    review_count = memory_context.get("review_count", 0)
    review_number = review_count + 1

    logger.info(
        "Starting review #%d for developer '%s' (language=%s, repo=%s)",
        review_number,
        developer_id,
        language,
        repo,
    )

    # ===================================================================
    # STEP 2 — BUILD PROMPTS: Inject memory into the review prompt
    # ===================================================================
    system_prompt = build_system_prompt(memory_context)
    user_prompt = build_review_prompt(diff_text, memory_context)

    # ===================================================================
    # STEP 3 — CALL GROQ: Send the diff + memory for review
    # ===================================================================
    review_text = call_groq(groq_client, system_prompt, user_prompt)

    # ===================================================================
    # STEP 4 — PARSE: Structure the review output
    # ===================================================================
    sections = parse_review_sections(review_text)

    # Build structured issues list for memory storage
    issues_found = []
    for severity, key in [("critical", "critical"), ("style", "style"), ("suggestion", "suggestions")]:
        for issue_text in sections.get(key, []):
            issues_found.append({
                "severity": severity,
                "type": key,
                "description": issue_text[:300],
            })

    # ===================================================================
    # STEP 5 — RETAIN: Store this review session into Hindsight memory
    # ===================================================================
    retain_success = retain_review_session(
        hindsight_client,
        developer_id,
        language,
        repo,
        issues_found,
        review_number,
    )

    if retain_success:
        logger.info("Review #%d retained successfully.", review_number)
    else:
        logger.warning("Failed to retain review #%d.", review_number)

    return {
        "review_text": review_text,
        "sections": sections,
        "memory_context": memory_context,
        "review_number": review_number,
        "issues_found": issues_found,
    }
