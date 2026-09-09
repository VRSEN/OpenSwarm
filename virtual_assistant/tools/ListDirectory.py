import os
from typing import Optional

from agency_swarm.tools import BaseTool
from pydantic import Field


class ListDirectory(BaseTool):
    """
    Lists files and directories in a given path.
    Use this tool to explore the project structure and understand the codebase layout.
    When the user refers to their codebase/project without giving a path, use
    their launch directory (the process working directory) — never default to
    the installed package directory (see #15).
    """

    directory_path: str = Field(
        ...,
        description="The absolute path to the directory to list",
    )
    recursive: Optional[bool] = Field(
        False,
        description="If True, list files recursively up to 3 levels deep. Default is False.",
    )
    max_depth: Optional[int] = Field(
        3,
        description="Maximum depth for recursive listing. Default is 3.",
    )

    def run(self):
        try:
            if not os.path.isabs(self.directory_path):
                return f"Error: directory_path must be an absolute path. Got: {self.directory_path}"

            if not os.path.exists(self.directory_path):
                return f"Error: Directory does not exist: {self.directory_path}"

            if not os.path.isdir(self.directory_path):
                return f"Error: Path is not a directory: {self.directory_path}"

            def list_dir_tree(path: str, prefix: str = "", depth: int = 0) -> str:
                if depth > self.max_depth:
                    return ""

                result = []
                try:
                    entries = sorted(os.listdir(path))
                except PermissionError:
                    return f"{prefix}[Permission Denied]\n"

                # Filter out hidden files and common ignore patterns
                ignore_patterns = {
                    "__pycache__",
                    ".git",
                    ".venv",
                    "venv",
                    "node_modules",
                    ".pytest_cache",
                    ".mypy_cache",
                    ".DS_Store",
                    "*.pyc",
                }

                filtered_entries = []
                for entry in entries:
                    if entry.startswith("."):
                        continue
                    if entry in ignore_patterns:
                        continue
                    filtered_entries.append(entry)

                for i, entry in enumerate(filtered_entries):
                    entry_path = os.path.join(path, entry)
                    is_last = i == len(filtered_entries) - 1

                    if is_last:
                        connector = "└── "
                        new_prefix = prefix + "    "
                    else:
                        connector = "├── "
                        new_prefix = prefix + "│   "

                    if os.path.isdir(entry_path):
                        result.append(f"{prefix}{connector}{entry}/\n")
                        if self.recursive and depth < self.max_depth:
                            result.append(
                                list_dir_tree(entry_path, new_prefix, depth + 1)
                            )
                    else:
                        result.append(f"{prefix}{connector}{entry}\n")

                return "".join(result)

            output = f"{self.directory_path}/\n"
            output += list_dir_tree(self.directory_path)

            if not output.strip():
                return f"Directory is empty: {self.directory_path}"

            return output.rstrip()

        except Exception as e:
            return f"Error listing directory: {str(e)}"


if __name__ == "__main__":
    # Test the tool with the launch directory (the user's codebase root),
    # not the installed package directory (see #15).
    import pathlib

    current_dir = str(pathlib.Path.cwd())

    tool = ListDirectory(directory_path=current_dir, recursive=True)
    print("Listing directory structure:")
    print(tool.run())


