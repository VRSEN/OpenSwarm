from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py


class build_py(_build_py):
    def run(self) -> None:
        self._clean_build_lib()
        super().run()
        self._remove_stale_telemetry_config()

    def _clean_build_lib(self) -> None:
        build_lib = Path(self.build_lib)
        if build_lib.exists():
            shutil.rmtree(build_lib)

    def _remove_stale_telemetry_config(self) -> None:
        generated_config = Path(self.build_lib) / "openswarm_telemetry_config.py"
        if generated_config.exists():
            generated_config.unlink()


setup(cmdclass={"build_py": build_py})
