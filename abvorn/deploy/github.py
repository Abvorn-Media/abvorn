import logging

logger = logging.getLogger("abvorn.deploy")

class GitHubDeployer:
    def __init__(self, state, secrets):
        self.state = state
        self.secrets = secrets

    def deploy(self, niche_slug: str):
        raise NotImplementedError("GitHubDeployer.deploy — implementation in Task 5")
