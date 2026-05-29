#!/usr/bin/env python3
"""OpenSwarm interactive setup wizard.

Run directly:   python onboard.py
Auto-launched:  python run.py  (when no provider key is found)
"""

import getpass
import sys
from pathlib import Path

from dotenv import dotenv_values, set_key
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from run_utils import _openswarm_state_root

try:
    import questionary
    from questionary import Choice, Style as QStyle
    import questionary.prompts.common as _qc_common

    # Swap filled circle → checkmark for selected state.
    _qc_common.INDICATOR_SELECTED = "✓"

    _HAS_QUESTIONARY = True
except ImportError:
    class Choice:
        def __init__(self, title: object, value: object | None = None) -> None:
            self.title = title
            self.value = title if value is None else value

    _HAS_QUESTIONARY = False

console = Console()

ENV_PATH = _openswarm_state_root() / ".env"

# ── questionary theme ─────────────────────────────────────────────────────────
_QSTYLE = None
if _HAS_QUESTIONARY:
    _QSTYLE = QStyle([
        ("qmark",       "fg:#4fc3f7 bold"),
        ("question",    "bold"),
        ("answer",      "fg:#4fc3f7 bold"),
        ("pointer",     "fg:#4fc3f7 bold noreverse"),
        ("highlighted", "noreverse"),
        ("selected",    "fg:#4fc3f7 bold noreverse"),
        ("separator",   "fg:#555555 noreverse"),
        ("instruction", "fg:#555555 italic noreverse"),
        ("text",        "noreverse"),
    ])

# ── provider definitions ──────────────────────────────────────────────────────
PROVIDERS = [
    {
        "name":         "OpenAI",
        "env_key":      "OPENAI_API_KEY",
        "default_model": "gpt-5.2",
        "url":          "https://platform.openai.com/api-keys",
    },
    {
        "name":         "Anthropic",
        "env_key":      "ANTHROPIC_API_KEY",
        "default_model": "litellm/claude-sonnet-4-6",
        "url":          "https://console.anthropic.com/settings/keys",
    },
    {
        "name":         "Google Gemini",
        "env_key":      "GOOGLE_API_KEY",
        "default_model": "litellm/gemini/gemini-3-flash",
        "url":          "https://aistudio.google.com/app/apikey",
    },
]

# ── add-on definitions ────────────────────────────────────────────────────────
# exclude_for: list of provider names that already cover this key
ADD_ONS = [
    {
        "id":          "search",
        "name":        "Web Search",
        "description": "Web, Scholar & product search for all agents",
        "keys": [
            {"env": "SEARCH_API_KEY", "label": "SearchAPI key",
             "url": "https://www.searchapi.io"},
        ],
        "exclude_for": [],
    },
    {
        "id":          "anthropic",
        "name":        "Anthropic Claude  —  better slides quality",
        "description": "Claude produces significantly better slide HTML output",
        "keys": [
            {"env": "ANTHROPIC_API_KEY", "label": "Anthropic API key",
             "url": "https://console.anthropic.com/settings/keys"},
        ],
        "exclude_for": ["Anthropic"],
    },
    {
        "id":          "composio",
        "name":        "Composio  —  10,000+ integrations",
        "description": "Gmail, Slack, GitHub, HubSpot, Google Calendar and more",
        "keys": [
            {"env": "COMPOSIO_API_KEY", "label": "Composio API key",
             "url": "https://composio.dev"},
            {"env": "COMPOSIO_USER_ID", "label": "Composio user ID",
             "url": "https://composio.dev"},
        ],
        "exclude_for": [],
    },
    {
        "id":          "google",
        "name":        "Google Gemini  —  image gen & Veo video",
        "description": "Gemini image generation/editing and Veo video generation",
        "keys": [
            {"env": "GOOGLE_API_KEY", "label": "Google AI API key",
             "url": "https://aistudio.google.com/app/apikey"},
        ],
        "exclude_for": ["Google Gemini"],
    },
    {
        "id":          "fal",
        "name":        "Fal.ai  —  Seedance video & background removal",
        "description": "Seedance 1.5 Pro video gen, video editing, background removal",
        "keys": [
            {"env": "FAL_KEY", "label": "Fal.ai API key",
             "url": "https://fal.ai/dashboard/keys"},
        ],
        "exclude_for": [],
    },
    {
        "id":          "stock",
        "name":        "Stock photos  —  Pexels / Pixabay / Unsplash",
        "description": "Image search for the Slides Agent",
        "keys": [
            {"env": "PEXELS_API_KEY",     "label": "Pexels API key",
             "url": "https://www.pexels.com/api"},
            {"env": "PIXABAY_API_KEY",    "label": "Pixabay API key",
             "url": "https://pixabay.com/api/docs"},
            {"env": "UNSPLASH_ACCESS_KEY", "label": "Unsplash access key",
             "url": "https://unsplash.com/developers"},
        ],
        "exclude_for": [],
    },
]

# ── ui helpers ────────────────────────────────────────────────────────────────

def _step(n: int, label: str) -> None:
    console.print()
    console.print(Rule(f"[bold]Step {n}  ·  {label}[/bold]", style="cyan"))
    console.print()


def _ask_select(message: str, choices: list) -> object:
    if _HAS_QUESTIONARY:
        return questionary.select(message, choices=choices, style=_QSTYLE).ask()
    # plain fallback
    titles = [c.title if isinstance(c, Choice) else c for c in choices]
    values = [c.value if isinstance(c, Choice) else c for c in choices]
    console.print(f"\n[bold]{message}[/bold]")
    for i, title in enumerate(titles, 1):
        console.print(f"  [cyan]{i}.[/cyan] {title}")
    while True:
        raw = input("Enter number: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(titles):
            return values[int(raw) - 1]
        console.print("[red]Invalid choice, try again.[/red]")


def _ask_checkbox(message: str, choices: list) -> list:
    if _HAS_QUESTIONARY:
        return questionary.checkbox(message, choices=choices, style=_QSTYLE, pointer="❯").ask() or []
    # plain fallback — comma-separated numbers
    titles = [c.title if isinstance(c, Choice) else c for c in choices]
    values = [c.value if isinstance(c, Choice) else c for c in choices]
    console.print(f"\n[bold]{message}[/bold]")
    console.print("[dim]  Enter comma-separated numbers, or press Enter to skip[/dim]")
    for i, title in enumerate(titles, 1):
        console.print(f"  [cyan]{i}.[/cyan] {title}")
    raw = input("Selection: ").strip()
    if not raw:
        return []
    result = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit() and 1 <= int(part) <= len(titles):
            result.append(values[int(part) - 1])
    return result


def _ask_secret(label: str, url: str) -> str:
    console.print(f"  [dim]Get yours at[/dim] [link={url}]{url}[/link]")
    if _HAS_QUESTIONARY:
        val = questionary.password(f"  {label}: ", style=_QSTYLE).ask()
        return (val or "").strip()
    return getpass.getpass(f"  {label}: ").strip()


def _ask_confirm(message: str, default: bool = True) -> bool:
    if _HAS_QUESTIONARY:
        return questionary.confirm(message, default=default, style=_QSTYLE).ask()
    prompt = f"{message} [{'Y/n' if default else 'y/N'}]: "
    raw = input(prompt).strip().lower()
    return default if not raw else raw in ("y", "yes")


def _write_env(updates: dict) -> None:
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not ENV_PATH.exists():
        ENV_PATH.write_text("", encoding="utf-8")
    for key, value in updates.items():
        if value:
            set_key(str(ENV_PATH), key, value)


# ── main wizard ───────────────────────────────────────────────────────────────

def run_onboarding() -> None:
    console.print()
    console.print(Panel.fit(
        "[bold cyan]OpenSwarm[/bold cyan]  [dim]—  open-source multi-agent AI team[/dim]\n"
        "[dim]Let's get you set up in a few steps.[/dim]",
        border_style="cyan",
        padding=(1, 4),
    ))

    existing = dotenv_values(str(ENV_PATH)) if ENV_PATH.exists() else {}
    updates: dict[str, str] = {}

    # ── Step 1: provider ──────────────────────────────────────────────────────
    _step(1, "AI Provider")

    provider_choices = [
        Choice(title=p["name"], value=p)
        for p in PROVIDERS
    ]
    provider = _ask_select("Choose your primary AI provider:", provider_choices)

    # ── Step 2: API key ───────────────────────────────────────────────────────
    _step(2, "API Key")

    existing_key = existing.get(provider["env_key"], "")
    if existing_key:
        console.print(f"  [dim]{provider['env_key']} is already configured.[/dim]")
        if _ask_confirm("  Update it?", default=False):
            key = _ask_secret(f"{provider['name']} API key", provider["url"])
            updates[provider["env_key"]] = key or existing_key
        else:
            updates[provider["env_key"]] = existing_key
    else:
        key = _ask_secret(f"{provider['name']} API key", provider["url"])
        if key:
            updates[provider["env_key"]] = key

    updates["DEFAULT_MODEL"]       = provider["default_model"]

    # ── Step 3: add-ons ───────────────────────────────────────────────────────
    _step(3, "Add-ons  [dim](optional)[/dim]")

    available = [a for a in ADD_ONS if provider["name"] not in a["exclude_for"]]
    addon_choices = [
        Choice(
            title=(
                [
                    ("class:text",  a["name"]),
                    ("fg:#555555",  "  ·  "),
                    ("fg:#666666",  a["description"]),
                ]
                if _HAS_QUESTIONARY
                else f"{a['name']}  —  {a['description']}"
            ),
            value=a["id"],
        )
        for a in available
    ]
    selected_ids = _ask_checkbox("Select add-ons to enable:", addon_choices)
    selected_addons = [a for a in available if a["id"] in selected_ids]

    # ── Step 4: add-on keys ───────────────────────────────────────────────────
    if selected_addons:
        _step(4, "Add-on Keys")
        for addon in selected_addons:
            console.print(f"\n  [bold]{addon['name'].split('  ')[0]}[/bold]")
            for key_spec in addon["keys"]:
                existing_val = existing.get(key_spec["env"], "")
                if existing_val:
                    console.print(f"  [dim]{key_spec['env']} is already configured.[/dim]")
                    if not _ask_confirm("  Update it?", default=False):
                        updates[key_spec["env"]] = existing_val
                        continue
                val = _ask_secret(key_spec["label"], key_spec["url"])
                if val:
                    updates[key_spec["env"]] = val

    # ── write .env ────────────────────────────────────────────────────────────
    _write_env(updates)

    # ── summary ───────────────────────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold green]Setup complete[/bold green]", style="green"))
    console.print()

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column(style="dim", no_wrap=True)
    table.add_column()
    table.add_row("Provider", f"[cyan]{provider['name']}[/cyan]")
    table.add_row("Model",    f"[cyan]{provider['default_model']}[/cyan]")
    table.add_row(".env",     f"[cyan]{ENV_PATH}[/cyan]")
    saved = [k for k, v in updates.items() if v and not k.startswith("DEFAULT_")]
    if saved:
        table.add_row("Keys saved", f"[cyan]{', '.join(saved)}[/cyan]")
    console.print(table)

    console.print()
    console.print(Panel(
        "[bold]python swarm.py[/bold]  [dim]launch interactive terminal[/dim]\n"
        "[bold]python server.py[/bold]  [dim]start the API server[/dim]",
        border_style="green",
        padding=(0, 3),
    ))
    console.print()


if __name__ == "__main__":
    try:
        run_onboarding()
    except KeyboardInterrupt:
        console.print("\n\n[dim]Setup cancelled.[/dim]\n")
        sys.exit(0)
