"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import os
from pathlib import Path

# **Initialization VERSION**
version_path = os.path.join(Path(__file__).resolve().parent.parent, "VERSION")
with open(version_path, "r") as file:
    version_str = file.readline().strip()
version = tuple(map(int, version_str.split(".")))

# **Initialization MIN_VERSION**
min_version_path = os.path.join(Path(__file__).resolve().parent.parent, "MIN_VERSION")
with open(min_version_path, "r") as file:
    min_version_str = file.readline().strip()
min_version = tuple(map(int, min_version_str.split(".")))