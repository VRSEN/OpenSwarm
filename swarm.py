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

    from architect import create_architect
    from frontend_dev import create_frontend_dev
    from backend_dev import create_backend_dev
    from code_reviewer import create_code_reviewer
    from qa_tester import create_qa_tester
    from devops import create_devops

    architect = create_architect()
    frontend_dev = create_frontend_dev()
    backend_dev = create_backend_dev()
    code_reviewer = create_code_reviewer()
    qa_tester = create_qa_tester()
    devops = create_devops()

    all_agents = [
        architect,
        frontend_dev,
        backend_dev,
        code_reviewer,
        qa_tester,
        devops,
    ]

    send_message_flows = [
        (architect, specialist, SendMessage)
        for specialist in all_agents
        if specialist is not architect
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
        name="CodeSwarm",
        shared_instructions="shared_instructions.md",
        load_threads_callback=load_threads_callback,
    )

    return agency

if __name__ == "__main__":
    agency = create_agency()
    agency.tui(show_reasoning=True, reload=False)
