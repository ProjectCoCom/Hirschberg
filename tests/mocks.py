"""
Summary: Python logic module 'Mocks'.

What it does: Provides backend utility operations and core logical helper interfaces for 'Mocks'.

How it fits in: Imported and utilized by surrounding backend structures.
"""



from __future__ import annotations

MOCK_JULES_SESSION_ID = "dry-run-session-001"
MOCK_PR_URL = "https://github.com/iceyxsm/TestRepo/pull/1"
MOCK_SHA = "abc123def456789"


class MockJulesAPI:
    def __init__(self):
        self.sessions_created = []
        self.messages_sent = []

    async def create_session(self, prompt, owner, repo, branch, jules_key):
        self.sessions_created.append({
            "prompt": prompt[:100],
            "owner": owner,
            "repo": repo,
            "branch": branch,
        })
        return MOCK_JULES_SESSION_ID

    async def poll_status(self, session_id, jules_key, timeout_minutes=20, **kwargs):
        return {
            "state": "COMPLETED",
            "outputs": [{"pull_request": {"url": MOCK_PR_URL}}],
        }

    async def send_message(self, session_id, message, jules_key):
        self.messages_sent.append({"session_id": session_id, "message": message})
        return True


class MockGitHubAPI:
    def __init__(self):
        self.branches_created = []
        self.merges = []
        self.prs_created = []
        self.files_written = []

    async def create_branch(self, owner, repo, branch_name, sha, token):
        self.branches_created.append(branch_name)
        return True

    async def get_default_sha(self, owner, repo, token):
        return MOCK_SHA

    async def merge(self, owner, repo, base, head, token):
        self.merges.append({"base": base, "head": head})
        return "merged"

    async def create_pr(self, owner, repo, head, base, title, token):
        self.prs_created.append({"head": head, "base": base, "title": title})
        return MOCK_PR_URL
