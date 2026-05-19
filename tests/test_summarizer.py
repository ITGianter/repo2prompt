"""Unit tests for the summarizer module."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

from repo2prompt.ignore import build_spec
from repo2prompt.scanner import build_tree
from repo2prompt.summarizer import Summarizer, build_file_index


def _make_project(files: dict[str, str]) -> str:
    root = tempfile.mkdtemp()
    for rel, content in files.items():
        abs_path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
    return root


@patch("repo2prompt.summarizer.openai.OpenAI")
def test_summarizer_success(mock_openai_cls):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "A simple hello world script."
    mock_resp.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_resp
    mock_openai_cls.return_value = mock_client

    s = Summarizer(model="gpt-4o-mini", api_key="sk-test")
    result = s.summarize('print("hi")', "hello.py")
    assert result == "A simple hello world script."
    mock_client.chat.completions.create.assert_called_once()


@patch("repo2prompt.summarizer.openai.OpenAI")
def test_summarizer_api_failure(mock_openai_cls):
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("API error")
    mock_openai_cls.return_value = mock_client

    s = Summarizer(model="gpt-4o-mini", api_key="sk-test")
    result = s.summarize("some content", "file.py")
    assert result == "[Summary generation failed]"


@patch("repo2prompt.summarizer.openai.OpenAI")
def test_summarizer_warning_file(mock_openai_cls):
    """Files with warnings (too large) should use warning as summary, no LLM call."""
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    root = tempfile.mkdtemp()
    big_path = os.path.join(root, "big.py")
    with open(big_path, "w", encoding="utf-8") as f:
        f.write("x = 1\n" * 200000)  # > 512KB

    from repo2prompt.scanner import Entry
    tree = Entry(name="root", rel_path="", is_dir=True, children=[
        Entry(name="big.py", rel_path="big.py", is_dir=False),
    ])

    s = Summarizer(model="gpt-4o-mini", api_key="sk-test")
    results = build_file_index(tree, root, s)

    assert len(results) == 1
    assert results[0].summary == "File too large to display"
    mock_client.chat.completions.create.assert_not_called()


@patch("repo2prompt.summarizer.openai.OpenAI")
def test_build_file_index_assigns_indexes(mock_openai_cls):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "summary"
    mock_resp.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_resp
    mock_openai_cls.return_value = mock_client

    root = _make_project({
        "a.py": "x = 1\n",
        "b.py": "y = 2\n",
        "c.py": "z = 3\n",
    })
    spec = build_spec(root)
    tree = build_tree(root, spec)

    s = Summarizer(model="gpt-4o-mini", api_key="sk-test")
    results = build_file_index(tree, root, s)

    assert len(results) == 3
    assert results[0].index == "FILE_001"
    assert results[1].index == "FILE_002"
    assert results[2].index == "FILE_003"


@patch("repo2prompt.summarizer.openai.OpenAI")
def test_build_file_index_dfs_order(mock_openai_cls):
    """Files should be indexed in DFS order (dirs sorted, then files sorted)."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "summary"
    mock_resp.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_resp
    mock_openai_cls.return_value = mock_client

    root = _make_project({
        "src/main.py": "x = 1\n",
        "src/lib/util.py": "y = 2\n",
        "README.md": "# Hello\n",
    })
    spec = build_spec(root)
    tree = build_tree(root, spec)

    s = Summarizer(model="gpt-4o-mini", api_key="sk-test")
    results = build_file_index(tree, root, s)

    paths = [fs.rel_path for fs in results]
    # DFS: src/ (dir) -> src/lib/ (dir) -> util.py -> main.py -> README.md
    assert paths == ["src/lib/util.py", "src/main.py", "README.md"]


# ---------------------------------------------------------------------------
# Cache tests
# ---------------------------------------------------------------------------

@patch("repo2prompt.summarizer.openai.OpenAI")
def test_cache_miss_then_hit(mock_openai_cls):
    """First call hits LLM and writes cache; second call reads cache, no LLM."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "A greeting script."
    mock_resp.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_resp
    mock_openai_cls.return_value = mock_client

    root = _make_project({"hello.py": 'print("hi")\n'})
    spec = build_spec(root)
    tree = build_tree(root, spec)

    s = Summarizer(model="gpt-4o-mini", api_key="sk-test")

    # First call — cache miss, LLM called
    results1 = build_file_index(tree, root, s)
    assert mock_client.chat.completions.create.call_count == 1
    assert results1[0].summary == "A greeting script."

    # Verify cache file was written
    cache_path = os.path.join(root, ".repo2prompt_cache.json")
    assert os.path.exists(cache_path)

    # Reset mock to track second call
    mock_client.chat.completions.create.reset_mock()

    # Second call — cache hit, no LLM
    results2 = build_file_index(tree, root, s)
    assert mock_client.chat.completions.create.call_count == 0
    assert results2[0].summary == "A greeting script."


@patch("repo2prompt.summarizer.openai.OpenAI")
def test_cache_invalidation_on_content_change(mock_openai_cls):
    """Changing file content invalidates the cache entry."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "original summary"
    mock_resp.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_resp
    mock_openai_cls.return_value = mock_client

    root = _make_project({"hello.py": 'print("hi")\n'})
    spec = build_spec(root)
    tree = build_tree(root, spec)

    s = Summarizer(model="gpt-4o-mini", api_key="sk-test")

    # First call
    build_file_index(tree, root, s)
    assert mock_client.chat.completions.create.call_count == 1

    # Modify file content
    with open(os.path.join(root, "hello.py"), "w") as f:
        f.write('print("changed")\n')

    # Rebuild tree (new content)
    spec2 = build_spec(root)
    tree2 = build_tree(root, spec2)

    mock_client.chat.completions.create.reset_mock()
    mock_choice.message.content = "changed summary"

    # Second call — cache miss due to content change
    results = build_file_index(tree2, root, s)
    assert mock_client.chat.completions.create.call_count == 1
    assert results[0].summary == "changed summary"


@patch("repo2prompt.summarizer.openai.OpenAI")
def test_cache_partial_api_failure(mock_openai_cls):
    """When one file's API call fails (after tenacity retries), successful
    files still get cached.  Exercises the real retry + exception-handling
    path in ``Summarizer._call_llm`` / ``summarize``.

    Detects the target file by parsing the prompt content, so the test is
    deterministic regardless of thread scheduling.
    """
    import threading

    lock = threading.Lock()

    def api_side_effect(**kwargs):
        prompt = kwargs["messages"][0]["content"]
        with lock:
            if "a.py" in prompt:
                raise Exception("API error for a.py")
        mock_resp = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "ok summary"
        mock_resp.choices = [mock_choice]
        return mock_resp

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = api_side_effect
    mock_openai_cls.return_value = mock_client

    # Patch tenacity's internal sleep to skip exponential backoff delays.
    # Without this the test would take ~14s (2+4+8s backoff for a.py retries).
    with patch("tenacity.nap.sleep"):
        root = _make_project({
            "a.py": "x = 1\n",
            "b.py": "y = 2\n",
        })
        spec = build_spec(root)
        tree = build_tree(root, spec)

        s = Summarizer(model="gpt-4o-mini", api_key="sk-test")
        results = build_file_index(tree, root, s)

    summaries = {fs.rel_path: fs.summary for fs in results}
    failed = [k for k, v in summaries.items() if v == "[Summary generation failed]"]
    succeeded = [k for k, v in summaries.items() if v == "ok summary"]
    assert len(failed) == 1
    assert len(succeeded) == 1

    # a.py: retried 3 times by tenacity then gave up (3 calls)
    # b.py: succeeded on first try (1 call)
    assert mock_client.chat.completions.create.call_count == 4

    # Cache should contain only the successful one
    import json
    cache_path = os.path.join(root, ".repo2prompt_cache.json")
    with open(cache_path, "r") as f:
        cache = json.load(f)
    assert len(cache) == 1
    assert succeeded[0] in cache


@patch("repo2prompt.summarizer.openai.OpenAI")
def test_corrupted_cache_handled(mock_openai_cls):
    """Corrupted cache JSON should be treated as cache miss, no crash."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "fresh summary"
    mock_resp.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_resp
    mock_openai_cls.return_value = mock_client

    root = _make_project({"hello.py": 'print("hi")\n'})

    # Write corrupted cache
    cache_path = os.path.join(root, ".repo2prompt_cache.json")
    with open(cache_path, "w") as f:
        f.write("{invalid json!!!")

    spec = build_spec(root)
    tree = build_tree(root, spec)

    s = Summarizer(model="gpt-4o-mini", api_key="sk-test")
    results = build_file_index(tree, root, s)

    # Should not crash, should call LLM
    assert mock_client.chat.completions.create.call_count == 1
    assert results[0].summary == "fresh summary"
