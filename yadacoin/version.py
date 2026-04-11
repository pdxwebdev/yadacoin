import os
from pathlib import Path

version_path = os.path.join(Path(__file__).resolve().parent.parent, "VERSION")
with open(version_path, "r") as file:
    version_str = file.readline().strip()
parts = version_str.split(".")
version = tuple(map(int, parts))
