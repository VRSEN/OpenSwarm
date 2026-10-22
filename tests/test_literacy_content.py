"""Literacy modules include real lesson structure, not slogans only."""

from backend.services.literacy_content import get_modules


def test_each_module_has_teaching_structure():
    modules = get_modules()
    assert len(modules) >= 14
    for m in modules:
        assert m.get("objectives") and len(m["objectives"]) >= 2
        assert m.get("sections") and len(m["sections"]) >= 1
        assert m.get("worked_example")
        assert m.get("exercise") and len(m["exercise"].get("steps", [])) >= 2
        assert m.get("reflection") and len(m["reflection"]) >= 1
        assert m.get("key_point")
