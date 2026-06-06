"""Shared helpers for list-traversal rules."""


def group_contiguous_lists(items, text):
    """Group list items into contiguous lists.

    Items separated by a blank line in the source are treated as separate lists.
    Each item must expose .start() and .end() returning absolute offsets in text.
    """
    lists = []
    for m in items:
        if not lists:
            lists.append([m])
            continue
        prev = lists[-1][-1]
        between = text[prev.end():m.start()]
        if "\n\n" not in between:
            lists[-1].append(m)
        else:
            lists.append([m])
    return lists
