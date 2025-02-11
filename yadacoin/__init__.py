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

version_path = os.path.join(Path(__file__).resolve().parent.parent, "VERSION")
with open(version_path, "r") as file:
    version_str = file.readline().strip()
parts = version_str.split(".")
version = tuple(map(int, parts))
