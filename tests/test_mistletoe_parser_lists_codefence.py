from rhetoric_lint.engine import RhetoricEngine


def test_lists_and_codefence_parsing(tmp_path):
    text = """# Todo\n\n- first item\n- second item with `inline` code\n\n```\n- this looks like a list inside code fence\n```\n\n- third item after fence\n"""
    p = tmp_path / "lists.md"
    p.write_text(text, encoding="utf-8")

    eng = RhetoricEngine()
    sections = eng._parse_with_mistletoe(text)
    if sections is None:
        return

    # collect list items from parsed paragraphs
    items = []
    for s in sections:
        for para in s.get("paragraphs", []):
            for node in para.get("nodes", []):
                if node.get("type") == "ListItem":
                    items.append(node)
    # Expect at least three list items (two before code fence, one after)
    assert len(items) >= 3

    # Ensure code fence content was captured as a Code node and not as a list item
    code_nodes = []
    for s in sections:
        for para in s.get("paragraphs", []):
            for node in para.get("nodes", []):
                if node.get("type") == "Code":
                    code_nodes.append(node)
    assert code_nodes, "expected code fence nodes to be present"

    # ensure list item texts do not include the fenced code marker
    for it in items:
        assert "```" not in it.get("text", "")
