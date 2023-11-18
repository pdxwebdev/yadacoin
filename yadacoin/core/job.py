class Job:
    @classmethod
    async def from_dict(cls, job):
        inst = cls()
        inst.id = job["job_id"]
        inst.diff = job["difficulty"]
        inst.target = job["target"]
        inst.blob = job["blob"]
        inst.seed_hash = job["seed_hash"]
        inst.index = job["height"]
        inst.algo = job["algo"]
        inst.start_nonce = job["start_nonce"]
        return inst

    def to_dict(self):
        return {
            "job_id": self.id,
            "difficulty": self.diff,
            "target": self.target,
            "blob": self.blob,
            "seed_hash": self.seed_hash,
            "height": self.index,
            "algo": self.algo,
        }
