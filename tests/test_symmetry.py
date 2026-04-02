import pytest
from rhetoric_lint.engine import RhetoricEngine

# Skip these tests if mistletoe isn't installed
pytest.importorskip("mistletoe")


def test_list_item_parallelism_ul_mixed(tmp_path):
    """Test that parallelism check flags mixed POS in unordered lists."""
    md = """# Sample

- Run the tests
- Build the project
- Deploy the app
- Packaging the release
"""

    p = tmp_path / "list.md"
    p.write_text(md, encoding="utf-8")

    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    checks = {it.get("check") for it in issues}

    # The parallelism check should flag the 'Packaging' item
    assert "Symmetry.Parallelism" in checks


def test_list_item_parallelism_ol_mixed(tmp_path):
    """Test that parallelism check flags mixed POS in ordered lists."""
    md = """# Features

1. Installation steps
2. Configuration process
3. Deployment guide
4. Run the tests
"""

    p = tmp_path / "list_ol.md"
    p.write_text(md, encoding="utf-8")

    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    
    # Should flag at least some items for parallelism
    parallelism_issues = [it for it in issues if it.get("check") == "Symmetry.Parallelism"]
    assert len(parallelism_issues) > 0


def test_list_item_parallelism_all_verbs(tmp_path):
    """Test that parallel lists with all verbs pass without issues."""
    md = """# Tasks

- Run the tests
- Build the project
- Deploy the app
- Package the release
"""

    p = tmp_path / "parallel.md"
    p.write_text(md, encoding="utf-8")

    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    parallelism_issues = [it for it in issues if it.get("check") == "Symmetry.Parallelism"]
    
    # Should have no parallelism issues
    assert len(parallelism_issues) == 0


def test_ordered_list_imperatives_task_heading(tmp_path):
    """Test that ol items under task headings must start with imperatives."""
    md = """# How to Deploy

1. Install the dependencies
2. Configure the settings
3. Running the server
"""

    p = tmp_path / "task_list.md"
    p.write_text(md, encoding="utf-8")

    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    
    # Should flag 'Running' as not imperative
    imperative_issues = [it for it in issues if it.get("check") == "Symmetry.OrderedListImperatives"]
    assert len(imperative_issues) > 0
    assert any("Running" in it.get("message", "") for it in imperative_issues)


def test_ordered_list_imperatives_all_imperatives(tmp_path):
    """Test that task lists with all imperatives pass."""
    md = """# Deployment Steps

1. Install the package
2. Configure the application
3. Run the server
4. Test the deployment
"""

    p = tmp_path / "good_task.md"
    p.write_text(md, encoding="utf-8")

    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    imperative_issues = [it for it in issues if it.get("check") == "Symmetry.OrderedListImperatives"]
    
    # Should have no imperative issues
    assert len(imperative_issues) == 0


def test_ordered_list_non_task_section(tmp_path):
    """Test that ol in non-task sections are not checked for imperatives."""
    md = """# Features

1. Advanced analytics dashboard
2. Real-time monitoring
3. Custom reporting tools
"""

    p = tmp_path / "features.md"
    p.write_text(md, encoding="utf-8")

    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    imperative_issues = [it for it in issues if it.get("check") == "Symmetry.OrderedListImperatives"]
    
    # Should not check imperatives for non-task lists
    assert len(imperative_issues) == 0


def test_unordered_list_not_checked_for_imperatives(tmp_path):
    """Test that ul items are never checked for imperatives."""
    md = """# How to Deploy

- Installation of dependencies
- Configuration settings
- Running the application
"""

    p = tmp_path / "ul_task.md"
    p.write_text(md, encoding="utf-8")

    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    imperative_issues = [it for it in issues if it.get("check") == "Symmetry.OrderedListImperatives"]
    
    # ul items should never trigger imperative checks
    assert len(imperative_issues) == 0


def test_task_list_detection_gerund_heading(tmp_path):
    """Test that headings starting with gerunds are detected as task sections."""
    md = """## Deploying the Application

1. Install dependencies
2. Starting the server
"""

    p = tmp_path / "gerund.md"
    p.write_text(md, encoding="utf-8")

    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    imperative_issues = [it for it in issues if it.get("check") == "Symmetry.OrderedListImperatives"]
    
    # Should detect as task list and flag 'Starting'
    assert len(imperative_issues) > 0


def test_task_list_detection_intro_text(tmp_path):
    """Test that intro text before list indicates task list."""
    md = """## Setup

Follow these steps to configure the application:

1. Download the package
2. Configuration of settings
"""

    p = tmp_path / "intro.md"
    p.write_text(md, encoding="utf-8")

    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    imperative_issues = [it for it in issues if it.get("check") == "Symmetry.OrderedListImperatives"]
    
    # Should detect as task list due to intro text
    assert len(imperative_issues) > 0


def test_short_list_not_checked_for_parallelism(tmp_path):
    """Test that lists with < 4 items are not checked for parallelism."""
    md = """# Sample

- Run tests
- Building
- Deploy
"""

    p = tmp_path / "short.md"
    p.write_text(md, encoding="utf-8")

    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    parallelism_issues = [it for it in issues if it.get("check") == "Symmetry.Parallelism"]
    
    # Short lists should not be checked
    assert len(parallelism_issues) == 0

