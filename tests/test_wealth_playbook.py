"""Wealth Playbook concept library."""

from backend.services.wealth_playbook import PLAYBOOK_CATEGORIES, get_playbook


def test_playbook_has_operator_concepts():
    entries = get_playbook()
    assert len(entries) >= 20
    ids = {e["id"] for e in entries}
    assert "lifestyle-trap" in ids
    assert "productizing-knowledge" in ids
    assert "se-tax-discipline" in ids


def test_playbook_has_covey_entries():
    covey = get_playbook(tag="7-habits")
    assert len(covey) >= 6
    ids = {e["id"] for e in covey}
    assert "covey-proactivity" in ids
    assert "covey-quadrant-ii" in ids
    assert "covey-character-ethic" in ids
    assert "covey-paradigm-shift" in ids


def test_playbook_has_esbi_entries():
    esbi = get_playbook(tag="esbi")
    assert len(esbi) >= 5
    ids = {e["id"] for e in esbi}
    assert "esbi-overview" in ids
    assert "esbi-s" in ids
    assert "esbi-b" in ids
    assert "esbi-i" in ids


def test_playbook_filter():
    mistakes = get_playbook(category="mistake")
    assert mistakes
    assert all(e["category"] == "mistake" for e in mistakes)
    assert "mistake" in PLAYBOOK_CATEGORIES
