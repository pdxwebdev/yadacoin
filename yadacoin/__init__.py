import git
repo = git.Repo('.')
tags = sorted(repo.tags, key=lambda t: t.commit.committed_datetime)
latest_tag = tags[-1]
version = tuple(str(latest_tag)[1:].split('.'))
