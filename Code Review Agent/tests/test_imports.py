import sys
sys.path.insert(0, '.')
from app.utils import parse_review_sections, format_issue_count

# Simulate real LLM output with multiple bullets per section
sample_llm_output = """
🔴 CRITICAL ISSUES (bugs, security vulnerabilities, data loss risks)
- [app/auth.py:45] **Bare except clause**: `except:` catches everything silently, masking real errors → Use `except (ValueError, ConnectionError) as e:` instead
- [app/auth.py:12] **Hardcoded API secret**: `API_SECRET_KEY = "sk-abc123"` is exposed in source → Move to environment variable `os.environ["API_SECRET_KEY"]`
- [app/models/user.py:23] **SQL injection risk**: String concatenation in query `"SELECT * FROM users WHERE email='" + email + "'"` → Use parameterized queries: `cursor.execute("SELECT * FROM users WHERE email=?", (email,))`

🟡 STYLE & STANDARDS
- [app/routes/users.py:8] **Unused imports**: `import re`, `import sys`, `import csv` are never used → Remove them
- [app/routes/users.py:15] **Missing docstrings**: `bulk_import_users()` and `get_user_by_id()` lack docstrings → Add Google-style docstrings
- [app/auth.py:30] **Poor variable naming**: Single-letter variables `u`, `d`, `x` throughout → Use `user`, `data`, `result`

🟢 SUGGESTIONS
- [app/routes/users.py:67] **Function length**: `bulk_import_users()` is 55 lines → Break into `_validate_user_data()` and `_persist_users()` helpers
- [app/auth.py:20] **Input validation**: No email format check on registration → Add `re.match(r"[^@]+@[^@]+\.[^@]+", email)` validation
"""

sections = parse_review_sections(sample_llm_output)

print("=== SECTION PARSER TEST ===")
print(f"Critical: {len(sections['critical'])} issues")
for i, issue in enumerate(sections['critical'], 1):
    print(f"  {i}. {issue[:100]}...")

print(f"\nStyle:    {len(sections['style'])} issues")
for i, issue in enumerate(sections['style'], 1):
    print(f"  {i}. {issue[:100]}...")

print(f"\nSuggestions: {len(sections['suggestions'])} issues")
for i, issue in enumerate(sections['suggestions'], 1):
    print(f"  {i}. {issue[:100]}...")

print(f"\nSummary: {format_issue_count(sections)}")

# Assertions
assert len(sections['critical']) == 3, f"Expected 3 critical, got {len(sections['critical'])}"
assert len(sections['style']) == 3, f"Expected 3 style, got {len(sections['style'])}"
assert len(sections['suggestions']) == 2, f"Expected 2 suggestions, got {len(sections['suggestions'])}"

print("\n[PASS] All assertions passed!")

# Test "No issues found" is filtered out
no_issues = """
🔴 CRITICAL ISSUES
No issues found.

🟡 STYLE & STANDARDS
- [file.py:1] Something wrong

🟢 SUGGESTIONS
No issues found.
"""
s2 = parse_review_sections(no_issues)
assert len(s2['critical']) == 0, f"Expected 0 critical (filtered), got {len(s2['critical'])}"
assert len(s2['style']) == 1
assert len(s2['suggestions']) == 0
print("[PASS] 'No issues found' filtering works!")
