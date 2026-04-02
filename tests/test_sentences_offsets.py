from rhetoric_lint.engine import RhetoricEngine


def test_sentences_have_absolute_offsets(tmp_path):
    text = """Paragraph start. First sentence here.\nSecond line continues the paragraph. And another sentence.\n\n# Heading\n\nNext paragraph."""
    p = tmp_path / "sents.md"
    p.write_text(text, encoding="utf-8")

    eng = RhetoricEngine()
    sections = eng._parse_with_mistletoe(text)
    if sections is None:
        return

    all_sents = []
    for s in sections:
        for para in s.get("paragraphs", []):
            for srec in para.get("sentences", []):
                # ensure absolute offsets are within document bounds
                assert 0 <= srec["start"] < len(text)
                assert 0 < srec["end"] <= len(text)
                # ensure line numbers are consistent
                assert srec["line"] == text[:srec["start"]].count("\n") + 1
                all_sents.append(srec)

    assert all_sents, "expected sentences to be attached to paragraphs"
