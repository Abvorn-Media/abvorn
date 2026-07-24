import logging

logger = logging.getLogger("abvorn.agents")

class AgentBase:
    def __init__(self, state, router):
        self.state = state
        self.router = router

    def run(self, *args, **kwargs):
        raise NotImplementedError("AgentBase.run — implementation in Task 4")
