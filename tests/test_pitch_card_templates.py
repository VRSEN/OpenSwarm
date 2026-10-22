"""Pitch card template rendering."""

from backend.services.pitch_card_templates import list_pitch_card_templates, render_pitch_card_html


def _sample_summary():
    return {
        "display_name": "Alex",
        "primary_trade": "Web consulting",
        "monthly_gross_income": 8200,
        "debt_total": 4200,
        "data_source_badge": "Your data",
        "stability_fund": {"pct_of_target": 50},
        "cashflow_quadrant": {
            "badge": "S → B",
            "primary_label": "Self-employed",
            "target_label": "Business owner",
            "income_mix_pct": {"E": 0, "S": 100, "B": 0, "I": 0},
            "next_mechanical_move": "Productize one offer.",
        },
        "disclaimer": "Educational only.",
    }


def test_list_pitch_cards():
    templates = list_pitch_card_templates()
    assert len(templates) == 4
    assert any(t["id"] == "operator_intro" for t in templates)


def test_render_operator_intro():
    html = render_pitch_card_html("operator_intro", _sample_summary(), {"stage": "Stability"})
    assert "1280px" in html
    assert "Alex" in html
    assert "S → B" in html


def test_render_esbi_path():
    html = render_pitch_card_html("esbi_path", _sample_summary(), {"stage": "Stability"})
    assert "ESBI" in html or "Cashflow" in html
