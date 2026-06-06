<div align="center">

# 🧠 MemoryReview
### Memory-Powered Code Review Agent

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Groq](https://img.shields.io/badge/Groq-F55036?style=for-the-badge&logo=groq&logoColor=white)](https://groq.com)
[![Hindsight](https://img.shields.io/badge/Hindsight_SDK-6C63FF?style=for-the-badge)](https://hindsight.dev)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

> **Submitted for HackWithIndia Presents: NEXUS HYBRID — The Ultimate Virtual Hackathon Experience**

*An AI code reviewer that actually remembers you.*

---

**Team: The Solution Team**

| 👤 Name | GitHub |
|---|---|
| Pranav Lakhe | 
| Aryan Raut | 
| Parth Vishnu | 
| Parth Dhoke | 

</div>

---

## 📌 Table of Contents

- [The Problem](#-the-problem)
- [Our Solution](#-our-solution)
- [Tech Stack](#-tech-stack)
- [How It Works](#-how-it-works)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [Demo Mode](#-demo-mode)
- [Testing](#-testing)
- [Future Roadmap](#-future-roadmap)

---

## ❌ The Problem

Traditional AI code review tools suffer from **"Goldfish Memory"** — they analyze each pull request in total isolation and forget everything the moment the output is generated.

This creates three critical pain points:

| Pain Point | Description |
|---|---|
| **Feedback Fatigue** | The bot flags the same issues (e.g., naming conventions) across dozens of PRs. Developers start ignoring it. |
| **No Personalization** | A stateless AI can't distinguish a junior developer needing detailed explanations from a senior dev who made a rare typo. |
| **No Growth Tracking** | There's no automated way to verify if a developer is actually learning from feedback or repeating the same vulnerabilities. |

---

## ✅ Our Solution

**MemoryReview** integrates the **Hindsight SDK** to create a persistent **Memory Bank** for every developer. It:

- 🔁 Remembers past mistakes across every PR review
- 📈 Tracks recurring architectural flaws and patterns
- 🎯 Dynamically personalizes the LLM prompt with historical context
- 🏆 Recognizes and praises genuine improvement

The result is an AI reviewer that behaves like a **seasoned pair-programmer who actually knows you**.

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.11+ |
| **Memory** | Hindsight SDK (`hindsight-client`) |
| **LLM** | Groq Cloud — `qwen/qwen3-32b` |
| **Frontend** | Streamlit + Custom Glassmorphism CSS |
| **VCS Integration** | PyGithub |
| **Testing** | pytest + unittest.mock |

> **Why Groq?** Blazing-fast inference speeds are critical for synchronous code review in CI/CD pipelines where developers are waiting.

---

## ⚙️ How It Works

MemoryReview runs a carefully orchestrated **5-step pipeline** on every review:

```
┌──────────────────────────────────────────────────────────────────┐
│                     MemoryReview Pipeline                        │
│                                                                  │
│  [1] Input          [2] Recall       [3] Inject                  │
│  GitHub PR URL  →   Hindsight SDK →  Build Dynamic  →            │
│  Pasted Code        queries the      LLM Prompt with             │
│  Demo Mode          Memory Bank      past context                │
│                                                                  │
│  [4] Infer          [5] Retain                                   │
│  Groq LLM    →      Push new issues  →  Display                  │
│  processes          back into the       Color-coded              │
│  diff + context     Memory Bank         UI                       │
└──────────────────────────────────────────────────────────────────┘
```

### Step 1 — Input & Context Gathering
Accepts a live GitHub PR URL, raw pasted code, or Demo Mode. For PR URLs, `github_utils.py` uses PyGithub to fetch and build a unified diff string (truncated to 15,000 chars max).

### Step 2 — The Recall Phase
Before generating any prompt, the agent queries the developer's Memory Bank:

```python
# app/memory.py
result = client.recall(
    bank_id=developer_id,
    query=f"What coding issues, patterns, and mistakes does this developer make in {language}?",
    tags=[language, "code-review"],
    budget="high"
)
```

### Step 3 — Context-Aware Prompt Injection
Recalled history is injected directly into the LLM system prompt:

```
Developer Context:
- This is review #N for this developer.
- Known recurring issues: {recurring_issues}
- Recently resolved issues: {resolved_issues}

Instructions:
- If you see recurring issues, point it out firmly.
- If the developer has avoided a past mistake, briefly praise them.
```

### Step 4 — LLM Inference & Parsing
Groq processes the diff with full context. An exponential backoff/retry mechanism handles rate limits (6K TPM on free tier). Output is parsed via regex in `utils.py` into three buckets:

| Badge | Category |
|---|---|
| 🔴 **Critical** | Bugs, security vulnerabilities, logic errors |
| 🟡 **Style** | Naming conventions, formatting, code smells |
| 🟢 **Suggestions** | Improvements, refactoring opportunities |

### Step 5 — The Retain Phase
New findings are pushed back to the Memory Bank for use in future reviews:

```python
client.retain(
    bank_id=developer_id,
    content=review_summary_string,
    context="code-review-session",
    tags=[language, repo, "code-review"],
    metadata={"review_number": str(review_number)}
)
```

---

## 📁 Project Structure

```
MemoryReview/
├── app/
│   ├── main.py              # Streamlit UI + Glassmorphism CSS
│   ├── memory.py            # Hindsight SDK integration (recall/retain/reflect)
│   ├── utils.py             # Regex parser → Critical / Style / Suggestion buckets
│   └── github_utils.py      # PyGithub PR diff fetcher
├── demo/
│   └── synthetic_history.py # Memory seeder — inserts 3 historical reviews
├── tests/
│   └── test_memory.py       # pytest suite with mocked Hindsight client
├── requirements.txt
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- A [Groq API Key](https://console.groq.com)
- A [Hindsight API Key](https://hindsight.dev)
- A [GitHub Personal Access Token](https://github.com/settings/tokens) (for PR fetching)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/Bytewi/Nexus.git
cd Nexus/Code\ Review\ Agent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
cp .env.example .env
# Edit .env with your API keys:
# GROQ_API_KEY=your_groq_key
# HINDSIGHT_API_KEY=your_hindsight_key
# GITHUB_TOKEN=your_github_token

# 4. Run the app
streamlit run app/main.py
```

---

## 🎬 Demo Mode

To showcase the power of memory at a glance **without submitting 5 real PRs**, run the memory seeder first:

```bash
python demo/synthetic_history.py
```

This seeds 3 historical reviews into Hindsight with a deliberate pattern — a recurring `bare except` clause that the developer never fixes. When you then run **Demo Mode** in the UI (Review #4), the LLM immediately identifies the pattern and generates a highly specific, personalized reprimand — perfectly demonstrating contextual memory in action.

---

## 🧪 Testing

```bash
pytest tests/
```

The test suite uses `unittest.mock` to mock all Hindsight network calls, ensuring tests run instantly without needing live API keys. Key coverage:

- **SDK mocking** — `hindsight.recall()`, `hindsight.retain()`, `hindsight.reflect()` are fully mocked
- **Parser validation** — The regex parser in `utils.py` is tested against edge-case LLM outputs, including "No issues found" responses and multi-bullet sections

---

## 🔮 Future Roadmap

| Feature | Description |
|---|---|
| **Native IDE Plugins** | VS Code / JetBrains extensions to query memory context in real-time as you type |
| **Team & Repo Memory** | Expand `bank_id` to repositories, learning codebase-specific architectural quirks |
| **Auto-Fix PRs** | Generate a patch and push a commit to fix issues, styled to the developer's historical preferences |

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

<div align="center">

Built with ❤️ by **The Solution Team** for **HackWithIndia — NEXUS HYBRID**

*Python • Streamlit • Groq • Hindsight SDK*

</div>
