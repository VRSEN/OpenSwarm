import os

from agency_swarm.tools import BaseTool

from shared_tools.workspace import get_workspace_root, resolve_skills_dirs


class ListSkills(BaseTool):
    """
    Lists all skills currently available to you.
    Skills are resolved from the user's launch directory first
    (<workspace>/mnt/skills), then the installed package directory,
    so launching from a codebase root finds the right folder (see #15).
    """

    def run(self):
        try:
            workspace = str(get_workspace_root())
            skills_dirs = [str(path) for path in resolve_skills_dirs()]

            skills = []
            searched = []
            for skills_path in skills_dirs:
                searched.append(skills_path)
                if not os.path.isdir(skills_path):
                    continue

                try:
                    entries = os.listdir(skills_path)
                except PermissionError:
                    return f"Error: Permission denied accessing skills folder: {skills_path}"

                for entry in sorted(entries):
                    entry_path = os.path.join(skills_path, entry)

                    if not os.path.isdir(entry_path):
                        continue

                    skill_file = None
                    if os.path.exists(os.path.join(entry_path, "SKILL.md")):
                        skill_file = os.path.join(entry_path, "SKILL.md")
                    elif os.path.exists(os.path.join(entry_path, "skill.md")):
                        skill_file = os.path.join(entry_path, "skill.md")

                    if not skill_file:
                        continue

                    try:
                        with open(skill_file, "r", encoding="utf-8") as f:
                            lines = f.readlines()

                        name = None
                        description = None

                        # Parse frontmatter: lines 2 and 3 carry "name:" and "description:"
                        if len(lines) > 1:
                            line2 = lines[1].strip()
                            if line2.startswith("name:"):
                                name = line2.split("name:", 1)[1].strip()

                        if len(lines) > 2:
                            line3 = lines[2].strip()
                            if line3.startswith("description:"):
                                description = line3.split("description:", 1)[1].strip()

                        skills.append({
                            "name": name or entry,
                            "description": description or "No description available",
                            "relative_path": os.path.relpath(skill_file, workspace),
                        })

                    except Exception as e:
                        skills.append({
                            "name": entry,
                            "description": f"Error reading skill file: {str(e)}",
                            "relative_path": os.path.relpath(skill_file, workspace),
                        })

            if not skills:
                return f"No skills found in {'; '.join(searched)}"

            output = [f"Found {len(skills)} skill(s) in {'; '.join(searched)}:\n"]

            for i, skill in enumerate(skills, 1):
                output.append(f"\n{i}. {skill['name']}")
                output.append(f"   Description: {skill['description']}")
                output.append(f"   Path: {skill['relative_path']}")

            return "\n".join(output)

        except Exception as e:
            return f"Error listing skills: {str(e)}"


if __name__ == "__main__":
    # Test the tool
    tool = ListSkills()
    result = tool.run()
    print(result)

