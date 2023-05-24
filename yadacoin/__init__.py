import git
from pathlib import Path

repo = git.Repo(Path(__file__).resolve().parent.parent, odbt=git.db.GitDB)
tags = sorted(repo.tags, key=lambda t: t.commit.committed_datetime)
latest_tag = tags[-1]
version = tuple([int(x) for x in latest_tag.name[1:].split(".")])
