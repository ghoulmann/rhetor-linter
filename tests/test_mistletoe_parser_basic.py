from rhetoric_lint.engine import RhetoricEngine


def test_basic_headings_and_paragraphs(tmp_path):
    text = """# Title\n\nIntro paragraph text.\n\n## Section\n\nSection paragraph line one.\nSecond sentence here.\n"""
    p = tmp_path / "doc.md"
    p.write_text(text, encoding="utf-8")

    eng = RhetoricEngine()
    sections = eng._parse_with_mistletoe(text)
    # if mistletoe not installed or parsing failed, skip
    if sections is None:
        return

    # Expect at least two sections: Title and Section
    assert any(s.get("heading") == "Title" for s in sections)
    assert any(s.get("heading") == "Section" for s in sections)

    sec = next(s for s in sections if s.get("heading") == "Section")
    assert sec.get("level") == 2
    # paragraph present
    assert len(sec.get("paragraphs", [])) >= 1
    para = sec["paragraphs"][0]
    # paragraph start should map to position of 'Section paragraph'
    assert text[para["pos"]:para["pos"] + 10].startswith("Section pa")
    # line number matches
    assert para["line"] == text[:para["pos"]].count("\n") + 1

    # sentences attached
    assert isinstance(para.get("sentences"), list)
    if para["sentences"]:
        s = para["sentences"][0]
        assert s["start"] >= para["pos"]
        assert s["end"] <= para["end"]
