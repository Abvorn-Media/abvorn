# Performance & Model Selection
- Model routing by task complexity (see `cost-aware-llm-pipeline` skill)
- Haiku for simple/cheap tasks (90% capability, 3x cost savings)
- Sonnet for complex coding tasks
- Context window: avoid filling past 80% for complex tasks
- Log model selection decisions to tune thresholds
- Set budget limits before batch processing — fail early, not overspend