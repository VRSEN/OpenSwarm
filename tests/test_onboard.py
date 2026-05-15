"""onboard.py — wizard data shape contract.

The wizard iterates `provider["keys"]` and substitutes `{model}` into
`provider["default_model"]`. A malformed entry crashes at runtime with
KeyError. These tests catch that before the wizard ever runs.
"""

from onboard import PROVIDERS, ADD_ONS


def test_every_provider_has_required_top_level_fields():
    for p in PROVIDERS:
        missing = {"name", "default_model", "keys"} - p.keys()
        assert not missing, f"Provider {p.get('name')!r} missing fields: {missing}"


def test_every_key_spec_has_env_and_label():
    for p in PROVIDERS:
        for spec in p["keys"]:
            assert "env" in spec, f"{p['name']} key missing 'env': {spec}"
            assert "label" in spec, f"{p['name']} key missing 'label': {spec}"


def test_templated_providers_have_model_label():
    """If default_model contains '{model}', the wizard prompts for it —
    so the spec must declare what label to show on that prompt."""
    for p in PROVIDERS:
        if "{model}" in p["default_model"]:
            assert "model_label" in p, (
                f"Provider {p['name']!r} uses {{model}} template but has "
                "no model_label — the wizard would crash on this entry."
            )


def test_anthropic_addon_excludes_azure_ai_foundry():
    """Picking azure_ai with a Claude model already covers Anthropic — the
    wizard should not prompt for a separate ANTHROPIC_API_KEY in that flow."""
    addon = next(a for a in ADD_ONS if a["id"] == "anthropic")
    assert "Azure AI Foundry" in addon["exclude_for"]
    assert "Anthropic" in addon["exclude_for"]


def test_openai_compat_key_has_no_url_field():
    """The key spec deliberately omits `url` since the relevant URL
    depends on which vendor (Ollama Cloud vs Groq vs Together vs ...).
    Rich would render any URL string here as a single misleading hyperlink."""
    p = next(p for p in PROVIDERS if "OpenAI-compatible" in p["name"])
    api_key_spec = next(k for k in p["keys"] if k["env"] == "OPENAI_COMPAT_API_KEY")
    assert "url" not in api_key_spec
