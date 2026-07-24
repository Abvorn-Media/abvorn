import logging

logger = logging.getLogger("abvorn.content")

class ContentPipeline:
    def __init__(self, state, router):
        self.state = state
        self.router = router

    def process(self, niche_slug: str):
        raise NotImplementedError("ContentPipeline.process — implementation in Task 3")
