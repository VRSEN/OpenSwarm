"""Regression test for #15: agent looked in the wrong directory.

The user launches OpenSwarm from their codebase root, but tools defaulted to
the installed package directory. This locks in:
- workspace root == process cwd (launch directory),
- skills resolved from workspace first, package second,
- ListDirectory guiding the model to the launch directory.
"""

import importlib.util
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load_workspace():
    spec = importlib.util.spec_from_file_location(
        "openswarm_workspace_under_test", REPO / "shared_tools" / "workspace.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_list_skills():
    agency = types.ModuleType("agency_swarm")
    tools = types.ModuleType("agency_swarm.tools")

    class BaseTool:
        pass

    tools.BaseTool = BaseTool
    agency.tools = tools
    sys.modules["agency_swarm"] = agency
    sys.modules["agency_swarm.tools"] = tools

    workspace_spec = importlib.util.spec_from_file_location(
        "shared_tools.workspace", REPO / "shared_tools" / "workspace.py"
    )
    workspace = importlib.util.module_from_spec(workspace_spec)
    sys.modules["shared_tools.workspace"] = workspace
    workspace_spec.loader.exec_module(workspace)

    shared_pkg = types.ModuleType("shared_tools")
    shared_pkg.__path__ = [str(REPO / "shared_tools")]
    shared_pkg.workspace = workspace
    sys.modules["shared_tools"] = shared_pkg

    spec = importlib.util.spec_from_file_location(
        "openswarm_list_skills_under_test",
        REPO / "virtual_assistant" / "tools" / "ListSkills.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workspace_root_is_launch_directory(tmp_path, monkeypatch):
    workspace = _load_workspace()
    monkeypatch.chdir(tmp_path)
    assert workspace.get_workspace_root() == tmp_path


def test_skills_dirs_prefer_workspace(tmp_path, monkeypatch):
    workspace = _load_workspace()
    monkeypatch.chdir(tmp_path)
    dirs = workspace.resolve_skills_dirs()
    assert dirs[0] == (tmp_path / "mnt" / "skills").absolute()
    assert dirs[-1] == (REPO / "mnt" / "skills").resolve() if (REPO / "mnt" / "skills").exists() else True


def test_list_skills_finds_workspace_skills(tmp_path, monkeypatch):
    skill_dir = tmp_path / "mnt" / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: Demo skill for workspace test\n---\n# Demo\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    module = _load_list_skills()
    result = module.ListSkills().run()
    assert "demo-skill" in result
    assert "Demo skill for workspace test" in result


def test_list_directory_guides_model_to_launch_dir():
    text = (REPO / "virtual_assistant" / "tools" / "ListDirectory.py").read_text(encoding="utf-8")
    assert "launch directory" in text
    assert "pathlib.Path.cwd()" in text
    assert "Path(__file__).parent.parent.absolute()" not in text
