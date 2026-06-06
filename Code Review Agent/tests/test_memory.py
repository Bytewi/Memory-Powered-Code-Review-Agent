"""
test_memory.py — Unit Tests for the Hindsight Memory Module.

Tests cover all public functions in app.memory:
  - init_hindsight
  - recall_developer_context
  - retain_review_session
  - get_review_count

All Hindsight SDK calls are mocked so tests run without a live server.

Usage:
    pytest tests/test_memory.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.memory import (
    init_hindsight,
    recall_developer_context,
    retain_review_session,
    get_review_count,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    """Return a MagicMock Hindsight client."""
    return MagicMock()


@pytest.fixture
def sample_issues():
    """Return a sample list of review issues."""
    return [
        {"severity": "critical", "type": "bare_except", "description": "Bare except clause in auth.py:45"},
        {"severity": "style", "type": "missing_docstring", "description": "Function lacks docstring"},
        {"severity": "suggestion", "type": "unused_import", "description": "'os' imported but not used"},
    ]


# ---------------------------------------------------------------------------
# Tests: init_hindsight
# ---------------------------------------------------------------------------

class TestInitHindsight:
    """Tests for init_hindsight()."""

    @patch("app.memory.Hindsight")
    @patch.dict(os.environ, {
        "HINDSIGHT_API_KEY": "test-api-key-12345",
        "HINDSIGHT_SERVER_URL": "https://test.hindsight.io",
    })
    def test_init_hindsight_success(self, mock_hindsight_class):
        """Verify client is created with correct params when env vars are set."""
        mock_instance = MagicMock()
        mock_hindsight_class.return_value = mock_instance

        client = init_hindsight()

        mock_hindsight_class.assert_called_once_with(
            base_url="https://test.hindsight.io",
            api_key="test-api-key-12345",
        )
        assert client is mock_instance

    @patch("app.memory.Hindsight")
    @patch.dict(os.environ, {}, clear=True)
    def test_init_hindsight_missing_key(self, mock_hindsight_class):
        """Verify ValueError is raised when HINDSIGHT_API_KEY is missing."""
        # Also clear any loaded dotenv values
        os.environ.pop("HINDSIGHT_API_KEY", None)

        with pytest.raises(ValueError, match="HINDSIGHT_API_KEY"):
            init_hindsight()

        mock_hindsight_class.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: recall_developer_context
# ---------------------------------------------------------------------------

class TestRecallDeveloperContext:
    """Tests for recall_developer_context()."""

    def test_recall_empty_for_new_developer(self, mock_client):
        """Verify defaults are returned when recall finds no memories."""
        mock_client.recall.return_value = MagicMock(results=None)

        context = recall_developer_context(
            client=mock_client,
            developer_id="new_developer",
            language="python",
        )

        assert context["review_count"] == 0
        assert context["recurring_issues"] == []
        assert context["resolved_issues"] == []
        assert context["raw_memories"] == []

        mock_client.recall.assert_called_once()

    def test_recall_returns_structured_data(self, mock_client):
        """Verify recall parses results into the expected structure."""
        # Create mock result objects
        result_1 = MagicMock()
        result_1.text = "Review #1: Found bare except clause and hardcoded secrets. bare except issue again."
        result_1.metadata = {"review_number": "1"}

        result_2 = MagicMock()
        result_2.text = "Review #2: bare except still present. SQL injection found. Fixed: hardcoded api key."
        result_2.metadata = {"review_number": "2"}

        mock_recall_response = MagicMock()
        mock_recall_response.results = [result_1, result_2]
        mock_client.recall.return_value = mock_recall_response

        context = recall_developer_context(
            client=mock_client,
            developer_id="test_dev",
            language="python",
            repo="test/repo",
        )

        assert context["review_count"] == 2
        assert len(context["raw_memories"]) == 2
        assert isinstance(context["recurring_issues"], list)
        assert isinstance(context["resolved_issues"], list)


# ---------------------------------------------------------------------------
# Tests: retain_review_session
# ---------------------------------------------------------------------------

class TestRetainReviewSession:
    """Tests for retain_review_session()."""

    def test_retain_stores_data(self, mock_client, sample_issues):
        """Verify retain is called with the correct parameters."""
        result = retain_review_session(
            client=mock_client,
            developer_id="test_dev",
            language="python",
            repo="test/repo",
            issues_found=sample_issues,
            review_number=1,
        )

        assert result is True
        mock_client.retain.assert_called_once()

        # Verify the call arguments
        call_kwargs = mock_client.retain.call_args
        assert call_kwargs.kwargs["bank_id"] == "test_dev"
        assert "code-review" in call_kwargs.kwargs["tags"]
        assert call_kwargs.kwargs["document_id"] == "review-test_dev-1"
        assert call_kwargs.kwargs["metadata"]["review_number"] == "1"
        assert call_kwargs.kwargs["metadata"]["language"] == "python"
        assert call_kwargs.kwargs["metadata"]["repo"] == "test/repo"

        # Verify content includes issue descriptions
        content = call_kwargs.kwargs["content"]
        assert "Code Review Session #1" in content
        assert "bare_except" in content
        assert "missing_docstring" in content
        assert "unused_import" in content

    def test_retain_handles_errors(self, mock_client, sample_issues):
        """Verify retain returns False when an exception occurs."""
        mock_client.retain.side_effect = Exception("Network error: connection refused")

        result = retain_review_session(
            client=mock_client,
            developer_id="test_dev",
            language="python",
            repo="test/repo",
            issues_found=sample_issues,
            review_number=1,
        )

        assert result is False


# ---------------------------------------------------------------------------
# Tests: get_review_count
# ---------------------------------------------------------------------------

class TestGetReviewCount:
    """Tests for get_review_count()."""

    def test_get_review_count(self, mock_client):
        """Verify count extraction from recall metadata."""
        result_1 = MagicMock()
        result_1.metadata = {"review_number": "1"}

        result_2 = MagicMock()
        result_2.metadata = {"review_number": "3"}

        result_3 = MagicMock()
        result_3.metadata = {"review_number": "2"}

        mock_response = MagicMock()
        mock_response.results = [result_1, result_2, result_3]
        mock_client.recall.return_value = mock_response

        count = get_review_count(mock_client, "test_dev")

        assert count == 3
        mock_client.recall.assert_called_once()

    def test_get_review_count_empty(self, mock_client):
        """Verify 0 is returned when no reviews exist."""
        mock_client.recall.return_value = MagicMock(results=None)

        count = get_review_count(mock_client, "new_dev")

        assert count == 0

    def test_get_review_count_handles_errors(self, mock_client):
        """Verify 0 is returned when recall raises an exception."""
        mock_client.recall.side_effect = Exception("Service unavailable")

        count = get_review_count(mock_client, "test_dev")

        assert count == 0
