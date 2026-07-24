# Abvorn Will + Drive — The Soul Layer

## Concept
The system needs more than pipelines — it needs volition. Two new modules:

### Will (`abvorn/will.py`)
The brain stem. Centralized volitional center:
- **Mission** — top-level purpose string that guides all decisions
- **Curiosity score** — 0 (exploit only) to 1 (explore only), auto-adjusted based on performance
- **`generate_goals()`** — publishes goals to AgentBus topic `will.goals`
- **`curiosity_pick(items)`** — mixes top-scoring (exploit) with novel (explore) picks
- **`reflect(cycles, revenue, engagement)`** — adjusts curiosity, logs insights
- **`mission_check(action)`** — blocks actions that violate the mission

### Drive (`abvorn/drive.py`)
Per-agent spine. Used via composition in any agent:
- **Grit counter** — increases on failure, decreases on success
- **`should_retry(attempt, error)`** — max attempts = 5 - grit (more grit → fewer attempts before pivot)
- **`alternative_path(blocked_action)`** — e.g., X fails → try LinkedIn
- **`log_outcome(action, succeeded)`** — feeds back to grit

### Integration
- Will publishes goals → AgentBus → agents consume with Drive guidance
- Agents report outcomes → AgentBus → Will.reflect() → adjust curiosity + grit
- Published on `will.goals` and `will.outcomes` topics

### Files
- Create: `abvorn/will.py` (~100 lines)
- Create: `abvorn/drive.py` (~80 lines)
- Create: `tests/test_will.py`
- Create: `tests/test_drive.py`