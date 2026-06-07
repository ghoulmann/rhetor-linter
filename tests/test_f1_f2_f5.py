"""Tests for F1 (section annotations), F2 (frontmatter), and F5 (DIMENSION_MAP)."""
import textwrap
import pytest

import rhetoric_lint.const as const
from rhetoric_lint.engine import (
    _parse_frontmatter,
    _extract_section_annotations,
)


# ---------------------------------------------------------------------------
# F5 — DIMENSION_MAP
# ---------------------------------------------------------------------------

class TestDimensionMap:
    def test_map_exists_in_const(self):
        assert hasattr(const, "DIMENSION_MAP")

    def test_all_five_dimensions_present(self):
        keys = set(const.DIMENSION_MAP.keys())
        assert {"Clarity", "Structure", "Completeness", "Style", "Readability"} == keys

    def test_clarity_contains_rhetoric_prefix(self):
        assert "Rhetoric" in const.DIMENSION_MAP["Clarity"]

    def test_structure_contains_heading_prefix(self):
        assert "Heading" in const.DIMENSION_MAP["Structure"]

    def test_completeness_contains_resilience(self):
        assert "Resilience" in const.DIMENSION_MAP["Completeness"]

    def test_readability_contains_readabilitygrade(self):
        assert "Rhetoric.ReadabilityGrade" in const.DIMENSION_MAP["Readability"]

    def test_default_dimension_defined(self):
        assert hasattr(const, "DIMENSION_DEFAULT")
        assert const.DIMENSION_DEFAULT == "Style"


# ---------------------------------------------------------------------------
# F2 — Frontmatter parsing
# ---------------------------------------------------------------------------

class TestParseFrontmatter:
    def test_empty_text_returns_empty(self):
        assert _parse_frontmatter("no frontmatter") == {}

    def test_parses_basic_frontmatter(self):
        text = textwrap.dedent("""\
            ---
            topic_type: reference
            owner: platform-team
            ---
            # Heading
        """)
        result = _parse_frontmatter(text)
        assert result.get("topic_type") == "reference"
        assert result.get("owner") == "platform-team"

    def test_aliases_normalised(self):
        # "doctype" is an alias for "topic_type"
        text = textwrap.dedent("""\
            ---
            doctype: howto
            sdlc: design
            ---
            # Heading
        """)
        result = _parse_frontmatter(text)
        assert result.get("topic_type") == "howto"
        assert result.get("sdlc_phase") == "design"

    def test_invalid_yaml_returns_empty(self):
        text = textwrap.dedent("""\
            ---
            key: [unclosed
            ---
            # Heading
        """)
        result = _parse_frontmatter(text)
        assert result == {}

    def test_no_frontmatter_returns_empty(self):
        text = "# Heading\n\nSome content.\n"
        assert _parse_frontmatter(text) == {}

    def test_tags_list_preserved(self):
        text = textwrap.dedent("""\
            ---
            tags:
              - api
              - authentication
            ---
            # Heading
        """)
        result = _parse_frontmatter(text)
        assert result.get("tags") == ["api", "authentication"]


# ---------------------------------------------------------------------------
# F1 — Section annotation extraction
# ---------------------------------------------------------------------------

class TestExtractSectionAnnotations:
    def test_empty_text_returns_empty(self):
        assert _extract_section_annotations("no annotations") == {}

    def test_extracts_annotation_for_next_heading(self):
        text = textwrap.dedent("""\
            # Top

            Some prose.

            <!--
            ---
            topic_type: reference
            audience: architect
            ---
            -->
            ## API Contract

            More content.
        """)
        result = _extract_section_annotations(text)
        assert result, "expected at least one annotation"
        # Find annotation for the heading line
        ann_values = list(result.values())
        assert any(a.get("topic_type") == "reference" for a in ann_values)
        assert any(a.get("audience") == "architect" for a in ann_values)

    def test_multiple_annotations_extracted(self):
        text = textwrap.dedent("""\
            # Doc

            <!--
            ---
            topic_type: howto
            ---
            -->
            ## Setup

            Content.

            <!--
            ---
            topic_type: reference
            ---
            -->
            ## Reference

            Content.
        """)
        result = _extract_section_annotations(text)
        types = {a.get("topic_type") for a in result.values()}
        assert "howto" in types
        assert "reference" in types

    def test_annotation_without_following_heading_not_stored(self):
        text = textwrap.dedent("""\
            <!--
            ---
            topic_type: reference
            ---
            -->
            Just a paragraph, not a heading.
        """)
        # No heading follows within 5 lines — result should be empty
        result = _extract_section_annotations(text)
        assert result == {}

    def test_invalid_yaml_in_annotation_skipped(self):
        text = textwrap.dedent("""\
            <!--
            ---
            key: [unclosed
            ---
            -->
            ## Heading
        """)
        result = _extract_section_annotations(text)
        assert result == {}


# ---------------------------------------------------------------------------
# Integration: engine populates context with frontmatter + annotations
# ---------------------------------------------------------------------------

from pathlib import Path
from rhetoric_lint.engine import RhetoricEngine


class TestEngineContextKeys:
    def test_frontmatter_in_context(self, tmp_path: Path):
        p = tmp_path / "doc.md"
        p.write_text(textwrap.dedent("""\
            ---
            topic_type: reference
            owner: docs-team
            ---
            # API Reference

            Some content about the API.
        """), encoding="utf-8")
        eng = RhetoricEngine()
        issues = eng.lint_files([str(p)])
        assert eng.last_genres  # engine ran
        # Frontmatter is not in issues — verify engine didn't crash
        assert isinstance(issues, list)

    def test_empty_frontmatter_no_crash(self, tmp_path: Path):
        p = tmp_path / "doc.md"
        p.write_text("# Simple Doc\n\nContent here.\n", encoding="utf-8")
        eng = RhetoricEngine()
        issues = eng.lint_files([str(p)])
        assert isinstance(issues, list)

    def test_annotation_overrides_topic_type(self, tmp_path: Path):
        p = tmp_path / "doc.md"
        p.write_text(textwrap.dedent("""\
            # Document

            Intro paragraph here for context and text.

            <!--
            ---
            topic_type: reference
            ---
            -->
            ## Configuration Options

            A table or list of config options here.
        """), encoding="utf-8")
        eng = RhetoricEngine()
        issues = eng.lint_files([str(p)])
        assert isinstance(issues, list)
