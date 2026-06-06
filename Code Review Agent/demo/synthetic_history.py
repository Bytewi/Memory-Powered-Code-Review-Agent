"""
synthetic_history.py — Seed Hindsight Memory with Synthetic Review History.

Run this script ONCE before the live demo to populate 3 past review sessions
into Hindsight memory. This way, when you run the Streamlit app, the agent
already "remembers" the developer's patterns and the demo starts at Review #4.

Usage:
    python demo/synthetic_history.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.memory import init_hindsight, retain_review_session

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEVELOPER_ID = "Pranavv28"
LANGUAGE = "python"
REPO = "Pranavv28/flask-user-api"

# ---------------------------------------------------------------------------
# Synthetic Review Data
# ---------------------------------------------------------------------------

review_1_issues = [
    {"severity": "critical", "type": "bare_except", "description": "Bare except clause in auth.py:45 — catches all exceptions silently, masking real errors. Use specific exception types."},
    {"severity": "critical", "type": "hardcoded_secret", "description": "Hardcoded API key in config.py:12 — API_SECRET_KEY should be loaded from environment variables."},
    {"severity": "style", "type": "missing_docstring", "description": "Functions authenticate_user() and create_session() lack docstrings."},
    {"severity": "style", "type": "no_type_hints", "description": "No type annotations on any function parameters or return values."},
    {"severity": "suggestion", "type": "unused_import", "description": "'import os' in auth.py is imported but never used."},
]

review_2_issues = [
    {"severity": "critical", "type": "bare_except", "description": "Bare except clause STILL present in auth.py:45 — this is a recurring pattern. Must use specific exception types like ValueError, ConnectionError."},
    {"severity": "critical", "type": "sql_injection", "description": "String concatenation used for SQL query in user.py:23 — vulnerable to SQL injection. Use parameterized queries."},
    {"severity": "style", "type": "variable_naming", "description": "Single-letter variables 'u', 'd', 'x' used throughout routes.py — use descriptive names."},
    {"severity": "style", "type": "missing_docstring", "description": "New functions added without docstrings — get_user_by_id(), update_profile()."},
    {"severity": "suggestion", "type": "input_validation", "description": "No input validation on user registration endpoint — email format and password strength not checked."},
]

review_3_issues = [
    {"severity": "critical", "type": "bare_except", "description": "Bare except clause remains in auth.py:45 AND new one added in routes.py:67. This is the 3rd consecutive review with this issue."},
    {"severity": "style", "type": "function_length", "description": "bulk_import_users() in routes.py is 55 lines long — should be broken into smaller helper functions."},
    {"severity": "style", "type": "variable_naming", "description": "Improved from last review but still some single-letter vars in nested loops."},
    {"severity": "suggestion", "type": "error_handling", "description": "Consider using a centralized error handler middleware instead of try/except in each route."},
]

REVIEWS = [
    (1, review_1_issues),
    (2, review_2_issues),
    (3, review_3_issues),
]

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Seed synthetic review history into Hindsight memory."""
    print()
    print("=" * 60)
    print("🧠 MemoryReview — Synthetic History Seeder")
    print("=" * 60)
    print()
    print(f"  Developer : {DEVELOPER_ID}")
    print(f"  Language  : {LANGUAGE}")
    print(f"  Repo      : {REPO}")
    print(f"  Reviews   : {len(REVIEWS)}")
    print()

    # --- Initialize Hindsight client ---
    try:
        print("🔌 Initializing Hindsight client...")
        client = init_hindsight()
        print("✅ Hindsight client connected!\n")
    except Exception as exc:
        print(f"❌ Failed to initialize Hindsight client: {exc}")
        print("   Make sure HINDSIGHT_API_KEY is set in your .env file.")
        sys.exit(1)

    # --- Seed each review ---
    success_count = 0
    fail_count = 0

    for review_number, issues in REVIEWS:
        print(f"📝 Seeding Review #{review_number} ({len(issues)} issues)...")

        try:
            result = retain_review_session(
                client=client,
                developer_id=DEVELOPER_ID,
                language=LANGUAGE,
                repo=REPO,
                issues_found=issues,
                review_number=review_number,
            )

            if result:
                print(f"   ✅ Review #{review_number} stored successfully!")
                success_count += 1
            else:
                print(f"   ⚠️  Review #{review_number} returned False — check logs.")
                fail_count += 1

        except Exception as exc:
            print(f"   ❌ Review #{review_number} failed: {exc}")
            fail_count += 1

        # Small delay between calls to avoid rate limiting
        if review_number < len(REVIEWS):
            time.sleep(1)

    # --- Final Summary ---
    print()
    print("=" * 60)
    print("📊 Seeding Summary")
    print("=" * 60)
    print(f"  ✅ Successful : {success_count}/{len(REVIEWS)}")
    if fail_count:
        print(f"  ❌ Failed     : {fail_count}/{len(REVIEWS)}")
    print()

    if success_count == len(REVIEWS):
        print("🎉 All reviews seeded! The demo is ready.")
        print(f"   Next live review will be Review #{len(REVIEWS) + 1}")
        print()
        print("🚀 Start the app with:")
        print("   streamlit run app/main.py")
    else:
        print("⚠️  Some reviews failed to seed. Check your .env and try again.")

    print()


if __name__ == "__main__":
    main()
