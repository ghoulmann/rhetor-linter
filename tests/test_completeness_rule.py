import rhetoric_lint.const as const
from rhetoric_lint.engine import RhetoricEngine
from rhetoric_lint.rules import completeness


def test_completeness_schema_mapping_detects_missing_table(tmp_path):
    text = """# API Guide

## API Reference

Here is an example response:

```json
{
  "id": 1,
  "name": "example"
}
```
"""
    p = tmp_path / "api.md"
    p.write_text(text, encoding="utf-8")

    eng = RhetoricEngine()
    sections = eng._parse_with_mistletoe(text)
    if sections is None:
        return

    context = {
        "path": str(p),
        "text": text,
        "nlp": eng.nlp,
        "const": const,
        "sections": sections,
    }
    issues = completeness.check(context)

    # expect a SchemaMapping issue for the API section
    assert any(i for i in issues if i.get("check") == "Completeness.SchemaMapping")

    # find the API Reference section and ensure the issue line matches
    api_sec = next(
        s for s in sections if s.get("heading") and "reference" in s.get("heading").lower()
    )
    expected_line = text[: api_sec.get("start", 0)].count("\n") + 1
    issue = next(i for i in issues if i.get("check") == "Completeness.SchemaMapping")
    assert issue["line"] == expected_line


# --- Completeness.ConceptOverload tests ---


def _run_full_engine(text: str, tmp_path):
    p = tmp_path / "test.md"
    p.write_text(text, encoding="utf-8")
    eng = RhetoricEngine()
    return eng.lint_files([str(p)])


def test_task_section_concept_overload(tmp_path):
    """Task section with too many prose paragraphs before the first list should flag."""
    md = """# Guide

## How to deploy the application

Deployment is a critical process that requires careful planning.

Before deploying, you need to understand the architecture of the system.

The deployment pipeline consists of several stages that work together.

There are important considerations about security and compliance.

- Step one: run the build command
- Step two: push to staging
- Step three: promote to production
"""
    issues = _run_full_engine(md, tmp_path)
    overload = [it for it in issues if it.get("check") == "Completeness.ConceptOverload"]
    assert len(overload) > 0
    assert "paragraphs" in overload[0].get("message", "").lower()


def test_non_task_prose_wall(tmp_path):
    """Section with many prose paragraphs and no structural elements should flag."""
    md = """# Documentation

## Architecture

The system uses a microservices architecture for scalability.

Each service communicates through a message queue for reliability.

The database layer provides persistent storage for all services.

Authentication is handled by a dedicated identity service.

Monitoring is performed through centralized logging and alerting.

Scaling is managed automatically based on CPU and memory metrics.
"""
    issues = _run_full_engine(md, tmp_path)
    overload = [it for it in issues if it.get("check") == "Completeness.ConceptOverload"]
    assert len(overload) > 0
    assert "structural" in overload[0].get("message", "").lower()


def test_task_section_quick_action_no_flag(tmp_path):
    """Task section with minimal prose before a code block should not flag."""
    md = """# Guide

## How to install the package

Install the package using pip:

```bash
pip install mypackage
```
"""
    issues = _run_full_engine(md, tmp_path)
    overload = [it for it in issues if it.get("check") == "Completeness.ConceptOverload"]
    assert overload == []


def test_section_with_only_lists_no_flag(tmp_path):
    """Section composed entirely of lists should not flag."""
    md = """# Reference

## Supported Features

- Feature A: data processing
- Feature B: report generation
- Feature C: user management
- Feature D: API integration
"""
    issues = _run_full_engine(md, tmp_path)
    overload = [it for it in issues if it.get("check") == "Completeness.ConceptOverload"]
    assert overload == []


# --- Completeness.StructureLead tests ---


def test_struct_lead_fires_on_code_block(tmp_path):
    """Heading immediately followed by a fenced code block must fire."""
    md = """# Guide

## Install the package

```bash
pip install mypackage
```
"""
    issues = _run_full_engine(md, tmp_path)
    lead = [it for it in issues if it.get("check") == "Completeness.StructureLead"]
    assert len(lead) > 0
    assert "code block" in lead[0]["message"]


def test_struct_lead_fires_on_large_list(tmp_path):
    """Heading immediately followed by 3+ list items must fire."""
    md = """# Guide

## Configuration options

- Option A: enables feature X
- Option B: sets the timeout value
- Option C: configures the retry limit
"""
    issues = _run_full_engine(md, tmp_path)
    lead = [it for it in issues if it.get("check") == "Completeness.StructureLead"]
    assert len(lead) > 0
    assert "list" in lead[0]["message"]


def test_struct_lead_no_fire_with_lead_sentence(tmp_path):
    """Lead sentence before the list suppresses the finding."""
    md = """# Guide

## Configuration options

The following options control the retry behavior of the client:

- Option A: enables feature X
- Option B: sets the timeout value
- Option C: configures the retry limit
"""
    issues = _run_full_engine(md, tmp_path)
    lead = [it for it in issues if it.get("check") == "Completeness.StructureLead"]
    assert lead == []


def test_struct_lead_no_fire_small_list(tmp_path):
    """1-2 item list is self-evident and should not fire."""
    md = """# Guide

## Platforms

- Linux
- macOS
"""
    issues = _run_full_engine(md, tmp_path)
    lead = [it for it in issues if it.get("check") == "Completeness.StructureLead"]
    assert lead == []


def test_struct_lead_no_fire_reference_heading(tmp_path):
    """Self-describing reference headings (CLI, API, etc.) are exempt."""
    md = """# Tool

## CLI Reference

```
tool --help
tool run --flag value
```
"""
    issues = _run_full_engine(md, tmp_path)
    lead = [it for it in issues if it.get("check") == "Completeness.StructureLead"]
    assert lead == []


def test_struct_lead_no_fire_colon_heading(tmp_path):
    """Heading ending with ':' already forms a stem sentence and is exempt."""
    md = """# Guide

## Required tools:

- Node.js 14 or higher
- Yarn package manager
- Docker Desktop
"""
    issues = _run_full_engine(md, tmp_path)
    lead = [it for it in issues if it.get("check") == "Completeness.StructureLead"]
    assert lead == []
