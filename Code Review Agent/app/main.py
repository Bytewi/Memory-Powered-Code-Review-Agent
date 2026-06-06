"""
main.py — Streamlit UI for the Memory-Powered Code Review Agent.

This is the front-end that ties everything together:
  - Sidebar: "What I Remember About You" memory panel
  - Main area: PR URL or code paste input → review output
  - Beautiful dark theme with glassmorphism and color-coded sections

Run with: streamlit run app/main.py
"""

import sys
import os
import logging
import streamlit as st

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.memory import (
    init_hindsight,
    recall_developer_context,
    reflect_on_developer,
    get_review_count,
)
from app.agent import run_review, init_groq
from app.github_utils import fetch_pr_from_url, format_diff_for_review
from app.utils import (
    parse_review_sections,
    format_issue_count,
    extract_language_from_diff,
    format_memory_for_display,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page Configuration & Custom CSS
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="🧠 MemoryReview — Code Review Agent",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* ---- Import Premium Font ---- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* ---- Global ---- */
    html, body {
        font-family: 'Inter', sans-serif;
    }
    p, h1, h2, h3, h4, h5, h6, li, a, button, input, textarea, label {
        font-family: 'Inter', sans-serif !important;
    }
    .stMarkdown div {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background: linear-gradient(135deg, #0f0c29 0%, #1a1a2e 40%, #16213e 100%);
    }

    /* ---- Sidebar Glass Panel ---- */
    section[data-testid="stSidebar"] {
        background: rgba(15, 12, 41, 0.85) !important;
        backdrop-filter: blur(20px) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    }

    section[data-testid="stSidebar"] .stMarkdown {
        color: #e0e0e0;
    }

    /* ---- Main Header ---- */
    .main-header {
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.15), rgba(118, 75, 162, 0.15));
        border: 1px solid rgba(102, 126, 234, 0.25);
        border-radius: 16px;
        padding: 28px 32px;
        margin-bottom: 28px;
        backdrop-filter: blur(10px);
    }

    .main-header h1 {
        background: linear-gradient(135deg, #667eea, #764ba2, #f093fb);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.4rem;
        font-weight: 800;
        margin-bottom: 4px;
    }

    .main-header p {
        color: rgba(255, 255, 255, 0.65);
        font-size: 1.05rem;
        font-weight: 300;
    }

    /* ---- Memory Panel Card ---- */
    .memory-panel {
        background: linear-gradient(145deg, rgba(102, 126, 234, 0.12), rgba(118, 75, 162, 0.08));
        border: 1px solid rgba(102, 126, 234, 0.2);
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 16px;
        backdrop-filter: blur(8px);
        transition: all 0.3s ease;
    }

    .memory-panel:hover {
        border-color: rgba(102, 126, 234, 0.45);
        transform: translateY(-1px);
        box-shadow: 0 4px 20px rgba(102, 126, 234, 0.12);
    }

    .memory-panel h3 {
        color: #a78bfa;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        margin-bottom: 10px;
    }

    /* ---- Review Count Badge ---- */
    .review-count {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        font-size: 2.8rem;
        font-weight: 800;
        text-align: center;
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 4px 24px rgba(102, 126, 234, 0.3);
    }

    .review-count .label {
        font-size: 0.75rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        opacity: 0.85;
        margin-top: 4px;
    }

    /* ---- Issue Cards ---- */
    .critical-card {
        background: linear-gradient(145deg, rgba(239, 68, 68, 0.1), rgba(239, 68, 68, 0.05));
        border-left: 4px solid #ef4444;
        border-radius: 0 10px 10px 0;
        padding: 16px 20px;
        margin-bottom: 12px;
    }

    .style-card {
        background: linear-gradient(145deg, rgba(245, 158, 11, 0.1), rgba(245, 158, 11, 0.05));
        border-left: 4px solid #f59e0b;
        border-radius: 0 10px 10px 0;
        padding: 16px 20px;
        margin-bottom: 12px;
    }

    .suggestion-card {
        background: linear-gradient(145deg, rgba(16, 185, 129, 0.1), rgba(16, 185, 129, 0.05));
        border-left: 4px solid #10b981;
        border-radius: 0 10px 10px 0;
        padding: 16px 20px;
        margin-bottom: 12px;
    }

    /* ---- Recurring Issue Badge ---- */
    .recurring-badge {
        background: rgba(239, 68, 68, 0.15);
        color: #fca5a5;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
        margin: 3px 4px 3px 0;
        border: 1px solid rgba(239, 68, 68, 0.25);
    }

    /* ---- Resolved Issue Badge ---- */
    .resolved-badge {
        background: rgba(16, 185, 129, 0.15);
        color: #6ee7b7;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
        margin: 3px 4px 3px 0;
        border: 1px solid rgba(16, 185, 129, 0.25);
    }

    /* ---- Status Indicator ---- */
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 6px;
        animation: pulse 2s infinite;
    }

    .status-dot.active {
        background: #10b981;
        box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    /* ---- Tabs ---- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: rgba(255, 255, 255, 0.03);
        border-radius: 10px;
        padding: 4px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: rgba(255, 255, 255, 0.6);
        font-weight: 500;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.2), rgba(118, 75, 162, 0.2));
        color: white;
    }

    /* ---- Buttons ---- */
    .stButton > button {
        background: linear-gradient(135deg, #667eea, #764ba2) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 12px 28px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 16px rgba(102, 126, 234, 0.3) !important;
    }

    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 24px rgba(102, 126, 234, 0.5) !important;
    }

    /* ---- Text Areas ---- */
    .stTextArea textarea {
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 10px !important;
        color: #e0e0e0 !important;
        font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
        font-size: 0.85rem !important;
    }

    .stTextInput input {
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 10px !important;
        color: #e0e0e0 !important;
    }

    /* ---- Expander ---- */
    .streamlit-expanderHeader {
        background: rgba(255, 255, 255, 0.03) !important;
        border-radius: 10px !important;
    }

    /* ---- Dividers ---- */
    hr {
        border-color: rgba(255, 255, 255, 0.06) !important;
    }

    /* ---- Hide Streamlit Branding ---- */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------
def init_session_state():
    """Initialize all session state variables."""
    if "hindsight_client" not in st.session_state:
        try:
            st.session_state.hindsight_client = init_hindsight()
            st.session_state.hindsight_connected = True
        except Exception as e:
            st.session_state.hindsight_client = None
            st.session_state.hindsight_connected = False
            logger.error("Failed to initialize Hindsight: %s", e)

    if "groq_client" not in st.session_state:
        try:
            st.session_state.groq_client = init_groq()
            st.session_state.groq_connected = True
        except Exception as e:
            st.session_state.groq_client = None
            st.session_state.groq_connected = False
            logger.error("Failed to initialize Groq: %s", e)

    if "review_history" not in st.session_state:
        st.session_state.review_history = []

    if "last_review" not in st.session_state:
        st.session_state.last_review = None


init_session_state()


# ---------------------------------------------------------------------------
# Sidebar — "What I Remember About You"
# ---------------------------------------------------------------------------
def render_sidebar():
    """Render the memory-powered sidebar."""
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 10px 0 20px;">
            <span style="font-size: 2.5rem;">🧠</span>
            <h2 style="background: linear-gradient(135deg, #667eea, #764ba2);
                       -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                       font-size: 1.4rem; font-weight: 700; margin-top: 4px;">
                MemoryReview
            </h2>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # Developer ID input
        developer_id = st.text_input(
            "👤 Developer ID",
            value="Pranavv28",
            help="Your unique identifier for memory tracking",
            key="developer_id_input",
        )

        st.markdown("---")

        # ---- Memory Panel ----
        st.markdown("""
        <div class="memory-panel">
            <h3>🧠 What I Remember About You</h3>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.hindsight_connected and developer_id:
            try:
                client = st.session_state.hindsight_client

                # Get review count
                review_count = get_review_count(client, developer_id)

                # Review count badge
                st.markdown(f"""
                <div class="review-count">
                    {review_count}
                    <div class="label">Reviews Completed</div>
                </div>
                """, unsafe_allow_html=True)

                if review_count > 0:
                    # Recall memory for display
                    memory_ctx = recall_developer_context(client, developer_id)
                    display = format_memory_for_display(memory_ctx)

                    # Top recurring issues
                    if display.get("top_issues"):
                        st.markdown("**🔄 Recurring Patterns**")
                        for issue in display["top_issues"][:5]:
                            st.markdown(
                                f'<span class="recurring-badge">⚠️ {issue}</span>',
                                unsafe_allow_html=True,
                            )
                        st.markdown("")

                    # Resolved issues
                    if display.get("resolved"):
                        st.markdown("**✅ Recently Resolved**")
                        for issue in display["resolved"][:5]:
                            st.markdown(
                                f'<span class="resolved-badge">✅ {issue}</span>',
                                unsafe_allow_html=True,
                            )
                        st.markdown("")

                    # Synthesized profile
                    with st.expander("📝 Developer Profile", expanded=False):
                        profile = reflect_on_developer(client, developer_id)
                        st.markdown(
                            f"<div style='color: #d1d5db; font-size: 0.85rem; line-height: 1.6;'>{profile}</div>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        "<div style='color: rgba(255,255,255,0.45); text-align: center; "
                        "padding: 20px; font-size: 0.9rem;'>"
                        "No memories yet.<br>Run your first review to start building your profile!"
                        "</div>",
                        unsafe_allow_html=True,
                    )

            except Exception as e:
                st.warning(f"Could not load memory: {e}")
        else:
            st.markdown(
                "<div style='color: rgba(255,255,255,0.4); text-align: center; padding: 12px;'>"
                "⚠️ Hindsight not connected.<br>Check your API key."
                "</div>",
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # Connection status
        st.markdown("**🔌 Connections**")
        hindsight_status = "🟢 Connected" if st.session_state.hindsight_connected else "🔴 Disconnected"
        groq_status = "🟢 Connected" if st.session_state.groq_connected else "🔴 Disconnected"

        col1, col2 = st.columns(2)
        with col1:
            st.caption(f"Hindsight: {hindsight_status}")
        with col2:
            st.caption(f"Groq: {groq_status}")

        return developer_id


# ---------------------------------------------------------------------------
# Main Area — Input & Review
# ---------------------------------------------------------------------------
def render_main_area(developer_id: str):
    """Render the main review interface."""

    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🧠 MemoryReview</h1>
        <p>A code review agent that gets smarter with every review. Powered by Hindsight memory.</p>
    </div>
    """, unsafe_allow_html=True)

    # Input tabs
    tab_pr, tab_paste, tab_demo = st.tabs([
        "🔗 GitHub PR URL",
        "📝 Paste Code",
        "🎯 Demo Mode",
    ])

    diff_text = None
    repo = ""
    language = ""

    # ---- Tab 1: GitHub PR URL ----
    with tab_pr:
        st.markdown("##### Fetch a Pull Request diff from GitHub")
        pr_url = st.text_input(
            "PR URL",
            placeholder="https://github.com/owner/repo/pull/123",
            key="pr_url_input",
            label_visibility="collapsed",
        )

        col1, col2 = st.columns([1, 4])
        with col1:
            fetch_btn = st.button("🔍 Fetch PR", key="fetch_pr_btn", use_container_width=True)

        if fetch_btn and pr_url:
            with st.spinner("Fetching PR diff from GitHub..."):
                try:
                    pr_data = fetch_pr_from_url(pr_url)
                    diff_text = format_diff_for_review(pr_data)
                    repo = f"{pr_url.split('github.com/')[-1].split('/pull')[0]}"
                    st.session_state["fetched_diff"] = diff_text
                    st.session_state["fetched_repo"] = repo
                    st.success(f"✅ Fetched PR: **{pr_data.get('title', 'Unknown')}** ({pr_data.get('files_changed', 0)} files)")
                except Exception as e:
                    st.error(f"❌ Failed to fetch PR: {e}")

        # Use previously fetched diff
        if "fetched_diff" in st.session_state:
            diff_text = st.session_state["fetched_diff"]
            repo = st.session_state.get("fetched_repo", "")

    # ---- Tab 2: Paste Code ----
    with tab_paste:
        st.markdown("##### Paste a code diff or raw code for review")
        pasted_code = st.text_area(
            "Code Input",
            height=300,
            placeholder="Paste your code diff or raw code here...\n\nSupports unified diff format or plain code.",
            key="code_paste_input",
            label_visibility="collapsed",
        )

        paste_repo = st.text_input(
            "Repository (optional)",
            placeholder="owner/repo",
            key="paste_repo_input",
        )

        if pasted_code:
            diff_text = pasted_code
            repo = paste_repo

    # ---- Tab 3: Demo Mode ----
    with tab_demo:
        st.markdown("##### Run a demo review using the pre-loaded sample diff")
        st.markdown(
            "<div style='color: rgba(255,255,255,0.5); font-size: 0.85rem; margin-bottom: 16px;'>"
            "Uses a realistic Python PR diff with known issues (bare except, hardcoded secrets, "
            "SQL injection, etc.). Perfect for demonstrating the memory effect."
            "</div>",
            unsafe_allow_html=True,
        )

        demo_diff_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "demo",
            "sample_pr_diff.txt",
        )

        if os.path.exists(demo_diff_path):
            with open(demo_diff_path, "r", encoding="utf-8") as f:
                demo_diff = f.read()

            with st.expander("📄 View Sample Diff", expanded=False):
                st.code(demo_diff, language="diff")

            col1, col2 = st.columns([1, 4])
            with col1:
                demo_btn = st.button("🚀 Run Demo Review", key="demo_btn", use_container_width=True)

            if demo_btn:
                diff_text = demo_diff
                repo = "Pranavv28/flask-user-api"
                language = "python"
        else:
            st.warning("Demo diff file not found. Please ensure `demo/sample_pr_diff.txt` exists.")

    st.markdown("---")

    # ---- Run Review ----
    if diff_text:
        if not language:
            language = extract_language_from_diff(diff_text)

        # Show detected info
        info_cols = st.columns(3)
        with info_cols[0]:
            st.markdown(f"**Language:** `{language}`")
        with info_cols[1]:
            st.markdown(f"**Repository:** `{repo or 'Not specified'}`")
        with info_cols[2]:
            st.markdown(f"**Developer:** `{developer_id}`")

        st.markdown("")

        if st.button("🔎 Run Code Review", key="run_review_btn", use_container_width=True):
            run_code_review(diff_text, developer_id, language, repo)

    # ---- Display Last Review ----
    if st.session_state.last_review:
        display_review_results(st.session_state.last_review)

    # ---- Review History ----
    if st.session_state.review_history:
        st.markdown("---")
        with st.expander(f"📚 Review History ({len(st.session_state.review_history)} reviews)", expanded=False):
            for i, review in enumerate(reversed(st.session_state.review_history)):
                st.markdown(
                    f"**Review #{review.get('review_number', '?')}** — "
                    f"{format_issue_count(review.get('sections', {}))} — "
                    f"`{review.get('language', '?')}`"
                )
                if i < len(st.session_state.review_history) - 1:
                    st.markdown("---")


# ---------------------------------------------------------------------------
# Review Execution
# ---------------------------------------------------------------------------
def run_code_review(diff_text: str, developer_id: str, language: str, repo: str):
    """Execute the review pipeline with progress display."""
    progress_placeholder = st.empty()
    status_placeholder = st.empty()

    with progress_placeholder.container():
        progress_bar = st.progress(0)

        # Step 1: Recall
        status_placeholder.markdown(
            '<div style="color: #a78bfa; font-weight: 500;">'
            '<span class="status-dot active"></span>'
            '🧠 Recalling developer history from memory...</div>',
            unsafe_allow_html=True,
        )
        progress_bar.progress(20)

    try:
        result = run_review(
            diff_text=diff_text,
            developer_id=developer_id,
            language=language,
            repo=repo,
            groq_client=st.session_state.groq_client,
            hindsight_client=st.session_state.hindsight_client,
        )

        progress_bar.progress(100)
        status_placeholder.markdown(
            '<div style="color: #10b981; font-weight: 500;">'
            '✅ Review complete! Memory updated.</div>',
            unsafe_allow_html=True,
        )

        # Store results
        result["language"] = language
        st.session_state.last_review = result
        st.session_state.review_history.append(result)

        st.rerun()

    except Exception as e:
        progress_bar.progress(0)
        status_placeholder.empty()
        st.error(f"❌ Review failed: {e}")
        logger.error("Review failed: %s", e, exc_info=True)


# ---------------------------------------------------------------------------
# Review Results Display
# ---------------------------------------------------------------------------
def display_review_results(review: dict):
    """Display formatted review results with color-coded sections."""
    st.markdown(f"""
    <div style="background: linear-gradient(145deg, rgba(102, 126, 234, 0.08), rgba(118, 75, 162, 0.05));
                border: 1px solid rgba(102, 126, 234, 0.15); border-radius: 14px;
                padding: 20px 24px; margin-bottom: 20px;">
        <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 12px;">
            <span style="font-size: 1.6rem;">📋</span>
            <div>
                <div style="font-size: 1.2rem; font-weight: 700; color: #e0e0e0;">
                    Review #{review.get('review_number', '?')}
                </div>
                <div style="color: rgba(255,255,255,0.5); font-size: 0.85rem;">
                    {format_issue_count(review.get('sections', {}))}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Memory context used
    memory_ctx = review.get("memory_context", {})
    if memory_ctx.get("review_count", 0) > 0:
        with st.expander("🧠 Memory Context Used", expanded=False):
            st.markdown(f"**Past Reviews:** {memory_ctx.get('review_count', 0)}")
            if memory_ctx.get("recurring_issues"):
                st.markdown(f"**Recurring Issues:** {', '.join(memory_ctx['recurring_issues'])}")
            if memory_ctx.get("resolved_issues"):
                st.markdown(f"**Resolved Issues:** {', '.join(memory_ctx['resolved_issues'])}")

    sections = review.get("sections", {})

    # 🔴 Critical Issues
    critical = sections.get("critical", [])
    with st.expander(f"🔴 Critical Issues ({len(critical)})", expanded=True):
        if critical:
            for issue in critical:
                st.markdown(
                    f'<div class="critical-card">{issue}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown("✅ No critical issues found!")

    # 🟡 Style & Standards
    style = sections.get("style", [])
    with st.expander(f"🟡 Style & Standards ({len(style)})", expanded=True):
        if style:
            for issue in style:
                st.markdown(
                    f'<div class="style-card">{issue}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown("✅ No style issues found!")

    # 🟢 Suggestions
    suggestions = sections.get("suggestions", [])
    with st.expander(f"🟢 Suggestions ({len(suggestions)})", expanded=True):
        if suggestions:
            for issue in suggestions:
                st.markdown(
                    f'<div class="suggestion-card">{issue}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown("✅ No suggestions — code looks great!")

    # Raw review text
    with st.expander("📜 Raw Review Output", expanded=False):
        st.markdown(review.get("review_text", "No review text available."))


# ---------------------------------------------------------------------------
# App Entry Point
# ---------------------------------------------------------------------------
def main():
    """Main application entry point."""
    developer_id = render_sidebar()
    render_main_area(developer_id)


if __name__ == "__main__":
    main()
