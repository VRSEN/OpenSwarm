from __future__ import annotations

from pathlib import Path


def _build_bootstrap_code() -> str:
    root_dir = str(Path(__file__).resolve().parents[1]).replace("\\", "\\\\")

    return f"""
import sys

if r"{root_dir}" not in sys.path:
    sys.path.insert(0, r"{root_dir}")

import helpers as _helpers
from helpers import execute_composio_tool, get_composio_client, get_composio_user_id

composio = get_composio_client()
user_id = get_composio_user_id()
_helpers.composio = composio
_helpers.user_id = user_id
""".strip()


def apply_ipython_composio_context_patch() -> None:
    """Prepend a bootstrap snippet to every IPythonInterpreter run.

    The snippet imports helpers and resolves the module-level `composio` and
    `user_id` singletons from the environment so that Composio tool calls made
    inside the kernel work without any manual setup.
    """
    from agency_swarm.tools import IPythonInterpreter

    if getattr(IPythonInterpreter, "_composio_context_patch_applied", False):
        return

    original_run = IPythonInterpreter.run

    async def run_with_composio_context(self):
        original_code = self.code
        bootstrap = _build_bootstrap_code()
        self.code = f"{bootstrap}\n\n{original_code}"
        try:
            return await original_run(self)
        finally:
            self.code = original_code

    IPythonInterpreter.run = run_with_composio_context
    IPythonInterpreter._composio_context_patch_applied = True


if __name__ == "__main__":
    apply_ipython_composio_context_patch()
    print("IPythonInterpreter Composio context patch applied.")
