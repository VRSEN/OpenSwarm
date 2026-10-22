"""Single-slide pitch card templates (1280×720) from intake profile."""

from __future__ import annotations

from typing import Any

PITCH_CARD_TEMPLATES: list[dict[str, str]] = [
    {
        "id": "operator_intro",
        "name": "Operator Intro",
        "description": "Name, trade, tagline, and ESBI badge — networking slide.",
    },
    {
        "id": "value_proposition",
        "name": "Value Proposition",
        "description": "Problem → solution → offer for your trade.",
    },
    {
        "id": "financial_highlight",
        "name": "Financial Highlight",
        "description": "Revenue, Stability Fund, stage, and debt snapshot.",
    },
    {
        "id": "esbi_path",
        "name": "ESBI Path",
        "description": "Cashflow quadrant badge, mix, and next move toward B/I.",
    },
]

_TEMPLATE_IDS = {t["id"] for t in PITCH_CARD_TEMPLATES}

_SLIDE_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { width: 1280px; height: 720px; overflow: hidden; }
  body {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: linear-gradient(135deg, #0d1f17 0%, #0a1218 55%, #121820 100%);
    color: #f4f7fb;
  }
  .slide {
    width: 1280px; height: 720px; padding: 56px 72px;
    display: flex; flex-direction: column; justify-content: space-between;
    position: relative;
  }
  .slide::before {
    content: ''; position: absolute; inset: 0;
    background-image: radial-gradient(circle at 20% 20%, rgba(46,204,113,0.12), transparent 45%),
      radial-gradient(circle at 80% 70%, rgba(61,139,253,0.1), transparent 40%);
    pointer-events: none;
  }
  .content { position: relative; z-index: 1; }
  .eyebrow {
    font-size: 14px; letter-spacing: 0.14em; text-transform: uppercase;
    color: #2ecc71; font-weight: 700; margin-bottom: 18px;
  }
  h1 {
    font-size: 56px; line-height: 1.05; font-weight: 800;
    max-width: 900px; margin-bottom: 20px;
  }
  .subtitle { font-size: 26px; line-height: 1.35; color: #b8c5d6; max-width: 820px; }
  .metrics {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-top: 36px;
  }
  .metric {
    background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px; padding: 22px 24px;
  }
  .metric .label { font-size: 13px; color: #8fa3b8; text-transform: uppercase; letter-spacing: 0.06em; }
  .metric .value { font-size: 32px; font-weight: 700; color: #2ecc71; margin-top: 8px; }
  .bullets { list-style: none; margin-top: 28px; }
  .bullets li {
    font-size: 24px; line-height: 1.45; padding: 10px 0 10px 28px;
    position: relative; color: #dce6f2;
  }
  .bullets li::before {
    content: ''; position: absolute; left: 0; top: 22px;
    width: 10px; height: 10px; border-radius: 50%; background: #2ecc71;
  }
  .footer {
    position: relative; z-index: 1; display: flex; justify-content: space-between;
    align-items: center; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 22px;
  }
  .badge {
    display: inline-block; font-size: 22px; font-weight: 800; color: #2ecc71;
    background: rgba(46,204,113,0.12); padding: 8px 18px; border-radius: 999px;
  }
  .footer small { color: #7d8fa3; font-size: 14px; }
  .disclaimer { font-size: 11px; color: #6b7c8f; max-width: 520px; }
"""


def list_pitch_card_templates() -> list[dict[str, str]]:
    return list(PITCH_CARD_TEMPLATES)


def render_pitch_card_html(
    template_id: str,
    summary: dict[str, Any],
    journey: dict[str, Any] | None = None,
) -> str:
    if template_id not in _TEMPLATE_IDS:
        raise ValueError(f"Unknown pitch card template: {template_id}")

    journey = journey or {}
    name = summary.get("display_name") or "Architect"
    trade = summary.get("primary_trade") or "Self-employed operator"
    cq = summary.get("cashflow_quadrant") or {}
    body = _render_body(template_id, name, trade, summary, journey, cq)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>{name} — Pitch Card</title>
  <style>{_SLIDE_CSS}</style>
</head>
<body>
{body}
</body>
</html>"""


def _money(value: float | int | None) -> str:
    n = float(value or 0)
    return f"${n:,.0f}" if abs(n - round(n)) < 0.01 else f"${n:,.2f}"


def _render_body(
    template_id: str,
    name: str,
    trade: str,
    summary: dict[str, Any],
    journey: dict[str, Any],
    cq: dict[str, Any],
) -> str:
    disclaimer = summary.get("disclaimer", "Educational only — not financial advice.")

    if template_id == "operator_intro":
        return f"""
<div class="slide">
  <div class="content">
    <div class="eyebrow">Architect Blueprint · Operator</div>
    <h1>{name}</h1>
    <p class="subtitle">{trade} — building systems, not trading time forever.</p>
    <div class="metrics">
      <div class="metric"><div class="label">Stage</div><div class="value">{journey.get('stage', 'Stability')}</div></div>
      <div class="metric"><div class="label">Revenue</div><div class="value">{_money(summary.get('monthly_gross_income'))}/mo</div></div>
      <div class="metric"><div class="label">Quadrant</div><div class="value">{cq.get('badge', 'S → B')}</div></div>
    </div>
  </div>
  <div class="footer">
    <span class="badge">{cq.get('badge', 'S → B')}</span>
    <small class="disclaimer">{disclaimer}</small>
  </div>
</div>"""

    if template_id == "value_proposition":
        offer = f"Fixed-scope {trade.lower()} packages — clarity, speed, measurable outcomes."
        return f"""
<div class="slide">
  <div class="content">
    <div class="eyebrow">Value proposition</div>
    <h1>{trade}</h1>
    <ul class="bullets">
      <li><strong>Problem:</strong> Owners need reliable {trade.lower()} without hourly scope creep.</li>
      <li><strong>Solution:</strong> Productized delivery with clear boundaries and owner-pay discipline.</li>
      <li><strong>Offer:</strong> {offer}</li>
    </ul>
  </div>
  <div class="footer">
    <span class="badge">{name}</span>
    <small class="disclaimer">{disclaimer}</small>
  </div>
</div>"""

    if template_id == "financial_highlight":
        stability = summary.get("stability_fund") or {}
        return f"""
<div class="slide">
  <div class="content">
    <div class="eyebrow">Financial highlight</div>
    <h1>{name}'s machine</h1>
    <div class="metrics">
      <div class="metric"><div class="label">Monthly revenue</div><div class="value">{_money(summary.get('monthly_gross_income'))}</div></div>
      <div class="metric"><div class="label">Stability Fund</div><div class="value">{stability.get('pct_of_target', 0)}%</div></div>
      <div class="metric"><div class="label">Total debt</div><div class="value">{_money(summary.get('debt_total'))}</div></div>
    </div>
    <p class="subtitle" style="margin-top:28px">Stage: {journey.get('stage', 'Stability')} — {journey.get('next_mechanical_action', 'Fund Stability Fund.')}</p>
  </div>
  <div class="footer">
    <span class="badge">{summary.get('data_source_badge', 'Your data')}</span>
    <small class="disclaimer">{disclaimer}</small>
  </div>
</div>"""

    mix = cq.get("income_mix_pct") or {}
    return f"""
<div class="slide">
  <div class="content">
    <div class="eyebrow">Cashflow Quadrant · ESBI</div>
    <h1>{cq.get('badge', 'S → B')}</h1>
    <p class="subtitle">{cq.get('primary_label', 'Self-employed')} → {cq.get('target_label', 'Business owner')}</p>
    <div class="metrics">
      <div class="metric"><div class="label">E</div><div class="value">{mix.get('E', 0)}%</div></div>
      <div class="metric"><div class="label">S</div><div class="value">{mix.get('S', 0)}%</div></div>
      <div class="metric"><div class="label">B + I</div><div class="value">{float(mix.get('B', 0)) + float(mix.get('I', 0)):.0f}%</div></div>
    </div>
    <p class="subtitle" style="margin-top:24px">{cq.get('next_mechanical_move', '')}</p>
  </div>
  <div class="footer">
    <span class="badge">{journey.get('stage', 'Stability')}</span>
    <small class="disclaimer">{disclaimer}</small>
  </div>
</div>"""
