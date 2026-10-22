"""
Architect Blueprint — Cash Flow Mastery wealth machine.

Run TUI: python financial_swarm.py
Run API + UI: python server.py  (AGENCY=financial by default)
"""

import os

from run_utils import _bootstrap, _openswarm_state_root, _preload_agentswarm_bin

_RUNTIME_CONFIGURED = False


def _configure_runtime() -> None:
    global _RUNTIME_CONFIGURED
    if _RUNTIME_CONFIGURED:
        return

    from dotenv import load_dotenv
    from agents import set_tracing_disabled, set_tracing_export_api_key
    from patches.patch_agent_memory import apply_agent_memory_patch
    from patches.patch_ipython_interpreter_composio import apply_ipython_composio_context_patch
    from patches.patch_utf8_file_reads import apply_utf8_file_read_patch

    load_dotenv(dotenv_path=_openswarm_state_root() / ".env")

    apply_utf8_file_read_patch()
    apply_ipython_composio_context_patch()
    apply_agent_memory_patch()

    _tracing_key = os.getenv("OPENAI_API_KEY")
    if _tracing_key:
        set_tracing_export_api_key(_tracing_key)
    else:
        set_tracing_disabled(True)

    _RUNTIME_CONFIGURED = True


if __name__ == "__main__":
    _preload_agentswarm_bin()
    _bootstrap()

_configure_runtime()


def create_agency(load_threads_callback=None):
    _configure_runtime()

    from agency_swarm import Agency
    from agency_swarm.tools import Handoff, SendMessage

    from architect_orchestrator import create_architect_orchestrator
    from arbitrage_scout import create_arbitrage_scout
    from behavioral_mirror import create_behavioral_mirror
    from cash_flow_engineer import create_cash_flow_engineer
    from discipline_controller import create_discipline_controller
    from docs_agent import create_docs_agent
    from financial_analyst import create_financial_analyst
    from image_generation_agent import create_image_generation_agent
    from legacy_architect import create_legacy_architect
    from leverage_strategist import create_leverage_strategist
    from capital_allocator import create_capital_allocator
    from opportunity_scanner import create_opportunity_scanner
    from reputation_validator import create_reputation_validator
    from risk_officer import create_risk_officer
    from slides_agent import create_slides_agent
    from studio_orchestrator import create_studio_orchestrator
    from tax_strategist import create_tax_strategist
    from video_generation_agent import create_video_generation_agent
    from wealth_architect import create_wealth_architect

    orchestrator = create_architect_orchestrator()
    studio_orchestrator = create_studio_orchestrator()
    behavioral_mirror = create_behavioral_mirror()
    cash_flow_engineer = create_cash_flow_engineer()
    opportunity_scanner = create_opportunity_scanner()
    risk_officer = create_risk_officer()
    capital_allocator = create_capital_allocator()
    leverage_strategist = create_leverage_strategist()
    reputation_validator = create_reputation_validator()
    legacy_architect = create_legacy_architect()
    financial_analyst = create_financial_analyst()
    tax_strategist = create_tax_strategist()
    discipline_controller = create_discipline_controller()
    arbitrage_scout = create_arbitrage_scout()
    wealth_architect = create_wealth_architect()
    docs_agent = create_docs_agent()
    slides_agent = create_slides_agent()
    image_agent = create_image_generation_agent()
    video_agent = create_video_generation_agent()

    core_six = [
        behavioral_mirror,
        cash_flow_engineer,
        opportunity_scanner,
        risk_officer,
        capital_allocator,
        leverage_strategist,
        reputation_validator,
        legacy_architect,
    ]
    wealth_specialists = [
        financial_analyst,
        tax_strategist,
        discipline_controller,
        arbitrage_scout,
        wealth_architect,
    ]
    content_specialists = [
        docs_agent,
        slides_agent,
        image_agent,
        video_agent,
    ]
    specialists = core_six + wealth_specialists + content_specialists
    entry_agents = [orchestrator, studio_orchestrator]

    send_message_flows = [
        (entry, specialist, SendMessage)
        for entry in entry_agents
        for specialist in specialists
    ]

    all_agents = entry_agents + specialists
    handoff_flows = [
        (a > b, Handoff)
        for a in all_agents
        for b in all_agents
        if a is not b
    ]

    agency = Agency(
        orchestrator,
        studio_orchestrator,
        *specialists,
        communication_flows=send_message_flows + handoff_flows,
        name="Architect Blueprint",
        shared_instructions="financial_shared_instructions.md",
        load_threads_callback=load_threads_callback,
    )

    return agency


def _main() -> None:
    agency = create_agency()
    agency.tui(show_reasoning=True, reload=False)


if __name__ == "__main__":
    _main()
