import os
from dotenv import load_dotenv
from agents import set_tracing_disabled, set_tracing_export_api_key
from patches.patch_agency_swarm_dual_comms import apply_dual_comms_patch
from patches.patch_file_attachment_refs import apply_file_attachment_reference_patch
from patches.patch_ipython_interpreter_composio import apply_ipython_composio_context_patch
from patches.patch_utf8_file_reads import apply_utf8_file_read_patch

load_dotenv()

apply_utf8_file_read_patch()
apply_dual_comms_patch()
apply_file_attachment_reference_patch()
apply_ipython_composio_context_patch()

_tracing_key = os.getenv("OPENAI_API_KEY")
if _tracing_key:
    set_tracing_export_api_key(_tracing_key)
else:
    set_tracing_disabled(True)


def create_agency(load_threads_callback=None):
    from agency_swarm import Agency
    from agency_swarm.tools import Handoff, SendMessage

    from data_analyst_agent import create_data_analyst
    from docs_agent import create_docs_agent
    from orchestrator import create_orchestrator
    from market_research_agent import create_market_research_agent
    from portfolio_manager_agent import create_portfolio_manager_agent
    from quantitative_analyst_agent import create_quantitative_analyst_agent
    from risk_manager_agent import create_risk_manager_agent
    from trade_execution_agent import create_trade_execution_agent

    orchestrator = create_orchestrator()
    trade_execution_agent = create_trade_execution_agent()
    portfolio_manager = create_portfolio_manager_agent()
    quantitative_analyst = create_quantitative_analyst_agent()
    market_research_analyst = create_market_research_agent()
    risk_manager = create_risk_manager_agent()
    data_analyst = create_data_analyst()
    docs_agent = create_docs_agent()

    all_agents = [
        orchestrator,
        trade_execution_agent,
        portfolio_manager,
        quantitative_analyst,
        market_research_analyst,
        risk_manager,
        data_analyst,
        docs_agent,
    ]

    send_message_flows = [
        (orchestrator, specialist, SendMessage)
        for specialist in all_agents
        if specialist is not orchestrator
    ]

    handoff_flows = [
        (a > b, Handoff)
        for a in all_agents
        for b in all_agents
        if a is not b
    ]

    agency = Agency(
        *all_agents,
        communication_flows=send_message_flows + handoff_flows,
        name="Trading Portfolio Swarm",
        shared_instructions="shared_instructions.md",
        load_threads_callback=load_threads_callback,
    )

    return agency

if __name__ == "__main__":
    agency = create_agency()
    agency.tui(show_reasoning=True, reload=False)
