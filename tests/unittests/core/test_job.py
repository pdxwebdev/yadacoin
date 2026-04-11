"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest

from yadacoin.core.job import Job


class TestJob(unittest.IsolatedAsyncioTestCase):
    async def test_from_dict(self):
        job_data = {
            "peer_id": "peer123",
            "job_id": "job456",
            "difficulty": 100,
            "target": "000000ffffffffff",
            "blob": "abcdef",
            "seed_hash": "seedhash123",
            "height": 500,
            "extra_nonce": "nonce99",
            "miner_diff": 50,
            "algo": "rx/0",
        }
        job = await Job.from_dict(job_data)
        self.assertIsInstance(job, Job)
        self.assertEqual(job.id, "peer123")
        self.assertEqual(job.job_id, "job456")
        self.assertEqual(job.diff, 100)
        self.assertEqual(job.target, "000000ffffffffff")
        self.assertEqual(job.blob, "abcdef")
        self.assertEqual(job.seed_hash, "seedhash123")
        self.assertEqual(job.index, 500)
        self.assertEqual(job.extra_nonce, "nonce99")
        self.assertEqual(job.miner_diff, 50)
        self.assertEqual(job.algo, "rx/0")

    async def test_to_dict(self):
        job_data = {
            "peer_id": "peer123",
            "job_id": "job456",
            "difficulty": 100,
            "target": "000000ffffffffff",
            "blob": "abcdef",
            "seed_hash": "seedhash123",
            "height": 500,
            "extra_nonce": "nonce99",
            "miner_diff": 50,
            "algo": "rx/0",
        }
        job = await Job.from_dict(job_data)
        d = job.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["job_id"], "job456")
        self.assertEqual(d["difficulty"], 100)
        self.assertEqual(d["target"], "000000ffffffffff")
        self.assertEqual(d["blob"], "abcdef")
        self.assertEqual(d["seed_hash"], "seedhash123")
        self.assertEqual(d["height"], 500)
        self.assertEqual(d["extra_nonce"], "nonce99")
        self.assertEqual(d["algo"], "rx/0")

    async def test_to_dict_does_not_include_peer_id(self):
        job_data = {
            "peer_id": "peer123",
            "job_id": "job1",
            "difficulty": 1,
            "target": "ff",
            "blob": "00",
            "seed_hash": "sh",
            "height": 1,
            "extra_nonce": "en",
            "miner_diff": 1,
            "algo": "rx/0",
        }
        job = await Job.from_dict(job_data)
        d = job.to_dict()
        self.assertNotIn("peer_id", d)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
