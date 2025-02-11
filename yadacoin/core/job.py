"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""


class Job:
    @classmethod
    async def from_dict(cls, job):
        inst = cls()
        inst.id = job["peer_id"]
        inst.job_id = job["job_id"]
        inst.diff = job["difficulty"]
        inst.target = job["target"]
        inst.blob = job["blob"]
        inst.seed_hash = job["seed_hash"]
        inst.index = job["height"]
        inst.extra_nonce = job["extra_nonce"]
        inst.miner_diff = job["miner_diff"]
        inst.algo = job["algo"]
        return inst

    def to_dict(self):
        return {
            "job_id": self.job_id,
            "difficulty": self.diff,
            "target": self.target,
            "blob": self.blob,
            "seed_hash": self.seed_hash,
            "height": self.index,
            "extra_nonce": self.extra_nonce,
            "algo": self.algo,
        }
