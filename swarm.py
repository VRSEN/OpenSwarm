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

    from orchestrator import create_orchestrator
    from virtual_assistant import create_virtual_assistant
    from deep_research import create_deep_research
    from data_analyst_agent import create_data_analyst
    from slides_agent import create_slides_agent
    from docs_agent import create_docs_agent
    from video_generation_agent import create_video_generation_agent
    from image_generation_agent import create_image_generation_agent
    from bmad_business_analyst import create_bmad_business_analyst
    from bmad_product_manager import create_bmad_product_manager
    from bmad_architect import create_bmad_architect
    from bmad_developer import create_bmad_developer
    from bmad_technical_writer import create_bmad_technical_writer

    orchestrator = create_orchestrator()
    virtual_assistant = create_virtual_assistant()
    deep_research = create_deep_research()
    data_analyst = create_data_analyst()
    slides_agent = create_slides_agent()
    docs_agent = create_docs_agent()
    video_generation_agent = create_video_generation_agent()
    image_generation_agent = create_image_generation_agent()
    bmad_business_analyst = create_bmad_business_analyst()
    bmad_product_manager = create_bmad_product_manager()
    bmad_architect = create_bmad_architect()
    bmad_developer = create_bmad_developer()
    bmad_technical_writer = create_bmad_technical_writer()

    all_agents = [
        orchestrator,
        virtual_assistant,
        slides_agent,
        deep_research,
        data_analyst,
        docs_agent,
        video_generation_agent,
        image_generation_agent,
        bmad_business_analyst,
        bmad_product_manager,
        bmad_architect,
        bmad_developer,
        bmad_technical_writer,
    ]

    # Avoid registering both SendMessage and Handoff on the same sender -> receiver
    # pair. The previous setup gave the orchestrator two communication channels to
    # every specialist, which could surface duplicated assistant text in the UI.
    #
    # Minimal safe fix:
    # - orchestrator -> specialists: Handoff only
    # - specialists -> specialists: Handoff
    # - no SendMessage flows by default
    #
    # This removes the overlapping dual-channel path that was the most likely cause
    # of duplicated responses.
    send_message_flows = []

    handoff_flows = [
        (a > b, Handoff)
        for a in all_agents
        for b in all_agents
        if a is not b
    ]

    agency = Agency(
        *all_agents,
        communication_flows=handoff_flows,
        name="OpenSwarm",
        shared_instructions="shared_instructions.md",
        load_threads_callback=load_threads_callback,
    )

    return agency

if __name__ == "__main__":
    agency = create_agency()
    agency.tui(show_reasoning=True, reload=False)
