import rhetoric_lint.const as const
from rhetoric_lint.engine import RhetoricEngine
from rhetoric_lint.rules import headings


def test_headings_use_ast_and_ignore_code_fence(tmp_path):
    text = """# Title

Intro paragraph.

```
# NotARealHeading
```

## Generic
"""
    p = tmp_path / "doc.md"
    p.write_text(text, encoding="utf-8")

    eng = RhetoricEngine()
    sections = eng._parse_with_mistletoe(text)
    if sections is None:
        return

    # ensure code-fence heading wasn't parsed as a real heading
    headings_list = [s.get("heading") for s in sections if s.get("heading")]
    assert "NotARealHeading" not in headings_list
    assert "Title" in headings_list
    assert "Generic" in headings_list

    context = {
        "path": str(p),
        "text": text,
        "nlp": eng.nlp,
        "const": const,
        "sections": sections,
    }
    issues = headings.check(context)

    # expect a Heading.Generic issue for 'Generic'
    assert any(i for i in issues if i.get("check") == "Heading.Generic")

    # find the section for Generic and assert reported line matches section start
    sec = next(s for s in sections if s.get("heading") == "Generic")
    expected_line = text[: sec.get("start", 0)].count("\n") + 1
    generic_issue = next(i for i in issues if i.get("check") == "Heading.Generic")
    assert generic_issue["line"] == expected_line
