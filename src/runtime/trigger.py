import os
import sys
import subprocess
from typing import Dict


def trigger_hyperopt_ml(paths: Dict) -> None:
	root = paths["root"]
	cmd = [sys.executable, "-m", "src.hyperopt_ml", "--trials", "10", "--test-mode"]
	subprocess.call(cmd, cwd=root)
