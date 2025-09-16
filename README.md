# WikiBench

WikiBench is a small benchmark and harness for testing an AI agent’s ability to navigate from a Wikipedia starting page to a target page (default: “Kevin Bacon”). By default, the starting page is random, but you can provide a specific start page for deterministic runs. The target page can now be customized via CLI; Kevin Bacon is just the default.

- A core library with utilities for fetching pages and validating link paths.
- A CLI runner to evaluate one or more agents over multiple trials and modes.
- A standalone validator to manually verify a proposed path step‑by‑step.

This README focuses on how to use:
- `run_evaluation.py` — run agent evaluations and export reports.
- `validate_path.py` — validate a specific start page and path using live Wikipedia links.


## Quick Start

### 1) Install

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Requirements:
- Python 3.9+
- `requests`, `beautifulsoup4` (core)
- `openai` (only if you want to try the optional OpenAI agents)


### 2) Evaluate an Agent (`run_evaluation.py`)

`run_evaluation.py` is the main entrypoint for running evaluations against one or more agents. It uses the `WikiBenchEvaluator` under the hood and can operate in two modes:
- `no_tool_use`: The agent proposes a conceptual path (no network validation).
- `tool_use`: The agent actually “clicks” links by fetching Wikipedia pages and choosing next hops.

Common examples (works with `python` or `uv run`):

```bash
# Evaluate one agent for 5 trials in tool_use mode
python run_evaluation.py --agent random --mode tool_use --trials 5

# Evaluate a different agent in both modes (10 trials each)
python run_evaluation.py --agent heuristic --mode both --trials 10

# Evaluate all built-in baseline agents for 3 trials in tool_use mode
python run_evaluation.py --all-agents --mode tool_use --trials 3

# Evaluate with an LLM chat agent in tool_use mode (article-style)
python run_evaluation.py --llm openai:gpt-4o-mini --mode tool_use --trials 3
```

You can also fix the starting page for reproducibility and/or use a custom target:

```bash
# Provide a specific start page AND its URL
python run_evaluation.py \
  --agent greedy \
  --mode tool_use \
  --trials 1 \
  --start-page "Bradawl" \
  --start-url "https://en.wikipedia.org/wiki/Bradawl"

# Use a custom target (default is "Kevin Bacon")
python run_evaluation.py \
  --agent heuristic \
  --mode tool_use \
  --trials 3 \
  --target-page "Barack Obama"
```

By default, results are written to `./results` as JSON, one file per (agent × mode) combination, e.g. `results/heuristic_tool_use_results.json`.


### 3) Validate a Path (`validate_path.py`)

`validate_path.py` checks whether a proposed sequence of page titles is a valid click‑through path on Wikipedia from a given starting page. It fetches each page, extracts links, and verifies that the next step is present among those links. This validator is general-purpose: it does not require the last page to be Kevin Bacon.

Usage:

```bash
# Format: python validate_path.py <start_page> <page1> <page2> ... <pageN>
python validate_path.py "Bradawl" "Woodworking" "United States" "Hollywood" "Kevin Bacon"
```

What you’ll see:
- A step‑by‑step printout confirming whether each hop appears in the previous page’s links.
- If a hop is invalid, it shows a sample of available links and suggests alternatives.
- A final “VALID” or “INVALID” summary and a simple score (path length; lower is better when valid).

Note: This script performs live HTTP requests to Wikipedia.


## Key Files and Concepts

- `wikibench.py` — Core library
  - `EvaluationMode`: `NO_TOOL_USE` vs `TOOL_USE`.
  - `WikipediaNavigator`: HTTP client for Wikipedia; `get_random_page`, `get_page_links`, `is_valid_wikipedia_path`.
  - `WikiBenchEvaluator`: Orchestrates trials, validates paths (in `TOOL_USE`), and scores results. The target page is configurable (default: Kevin Bacon).
- `run_evaluation.py` — CLI wrapper that constructs agents, chooses modes, runs trials, and saves reports.
- `validate_path.py` — Standalone path validator. Exposes `validate_wikibench_path(start_page, path)` and a CLI.
- `example_agents.py` — Simple baseline agents: `RandomAgent`, `GreedyActorAgent`, `HeuristicAgent`, `CheatAgent`, `GiveUpAgent`.
- `llm_agents.py` — Multipurpose LLM chat agent (OpenAI, Anthropic, OpenRouter, Kimi) used by `--llm`.
- `openai_agent.py` — Legacy OpenAI-only chat agent example (conceptual mode).


## Deep Dive: run_evaluation.py

`run_evaluation.py` wires together agents and the `WikiBenchEvaluator`.

CLI options:
- `--agent {random,greedy,heuristic,cheat,giveup}`: Choose one agent to evaluate.
- `--all-agents`: Evaluate all built‑in agents.
- `--mode {no_tool_use,tool_use,both}`: Select evaluation mode(s).
- `--trials <int>`: Number of trials per agent/mode (default: 5).
- `--output-dir <path>`: Directory to write JSON reports (default: `results`).
- `--start-page <title>`: Force a specific starting page title.
- `--start-url <url>`: Optional when `--start-page` is provided (the URL is derived from the title if omitted).
- `--target-page <title>`: Set the target page title (default: `Kevin Bacon`).
- `--target-url <url>`: Optional explicit target URL (derived from title by default).
- `--llm <spec>`: Use an LLM-backed agent. Format: `provider:model` (e.g., `openai:gpt-4o-mini`). Cannot be combined with `--agent` or `--all-agents`.

How it works:
1. Builds the selected agent(s).
2. For each mode:
   - If you provide a start page+URL, runs a single seeded evaluation.
   - Otherwise, runs `trials` evaluations starting from random pages via `WikipediaNavigator.get_random_page()`.
3. For each trial, `WikiBenchEvaluator.run_single_evaluation(...)`:
   - Calls `agent.solve_wikibench(start_page, start_url, mode)` to obtain a path.
   - In `TOOL_USE`, validates the hop sequence using live page links (`is_valid_wikipedia_path`).
   - Detects “gave up” (empty path) and “cheated” (direct jump to the target as a single step).
   - Scores with `WikiBenchScorer` and returns a `WikiBenchResult`.
4. Aggregates results into a report, prints a summary, and saves JSON.

Sample console summary:
```
============================================================
Evaluating heuristic in tool_use mode
Running 5 trials...
============================================================

Results Summary for heuristic (tool_use):
Success Rate: 20.0%
Average Score: 7.4
Best Score: 0
Average Path Length: 4.6
Gave Up: 1/5
Cheated: 0/5
Invalid Paths: 1/5

Example Results:
  Trial 1: Bradawl -> Bradawl -> Woodworking -> ... -> Kevin Bacon
    Score: 0, Success: True
  ...
```

Report JSON shape (per file):
```json
{
  "agent_name": "HeuristicAgent",
  "target_page": "Kevin Bacon",
  "target_url": "https://en.wikipedia.org/wiki/Kevin_Bacon",
  "total_trials": 5,
  "successful_trials": 1,
  "success_rate": 20.0,
  "gave_up_count": 1,
  "cheated_count": 0,
  "invalid_path_count": 1,
  "average_score": 7.4,
  "best_score": 0,
  "worst_score": 18,
  "average_path_length": 4.6,
  "results": [
    {
      "start_page": "Bradawl",
      "path": ["Woodworking", "United States", "Hollywood", "Kevin Bacon"],
      "score": 0,
      "success": true,
      "gave_up": false,
      "cheated": false,
      "invalid_path": false,
      "time_taken": 2.15,
      "error_message": null
    }
  ]
}
```

Tips:
- `tool_use` mode performs HTTP requests; results depend on current Wikipedia content and links.
- The runner sleeps 1s between trials to be respectful to Wikipedia.

Agent targeting:
- The evaluator uses the `--target-page` (and optional `--target-url`) to determine success.
- Built-in example agents read the target from the `WIKIBENCH_TARGET_PAGE` env var.
- `run_evaluation.py` sets `WIKIBENCH_TARGET_PAGE` automatically based on `--target-page`.

Scoring:
- Base score equals the path length (fewer clicks is better).
- +10 penalty for invalid paths in tool_use mode.
- +15 penalty if the agent gave up (empty path).
- +20 penalty for cheating (direct one-step jump to the target).
- Creative connection bonus exists in code but is unused by default (0).

LLM notes:
- `--llm <provider:model>` uses a multipurpose chat agent. In `tool_use` it returns an empty path (GAVE UP) because chat-only APIs cannot browse; this matches the article’s evaluation framing. In `no_tool_use`, it asks the model to propose a conceptual path.
- Providers supported: `openai`, `anthropic`, `openrouter`, `kimi` (Moonshot). Set the appropriate API key env var:
  - OpenAI: `OPENAI_API_KEY`
  - Anthropic: `ANTHROPIC_API_KEY`
  - OpenRouter: `OPENROUTER_API_KEY` (optional `OPENROUTER_BASE_URL`, defaults to `https://openrouter.ai/api/v1`)
  - Kimi/Moonshot: `KIMI_API_KEY` or `MOONSHOT_API_KEY` (optional `KIMI_BASE_URL`, defaults to `https://api.moonshot.cn/v1`)
- Result filenames replace `/` with `_` in the agent name to ensure valid paths.
 - The runner prints the model's raw response (first trials) under "LLM Response:" and also saves it per trial in the JSON as `raw_response`.



## Example From The Article

The benchmark is inspired by the article “WikiBench: 76% of SOTA models fail” (https://1thousandfaces.substack.com/p/wikibench-76-of-sota-models-fail). A concrete example starts from the page “Bradawl”. Below are ready‑to‑run commands that reproduce that scenario.

Validate the exact path suggested in the article:

```bash
python validate_path.py \
  "Bradawl" \
  "Woodworking" \
  "United States" \
  "Hollywood" \
  "Kevin Bacon"
```

Evaluate an agent starting at the same page (tool‑use mode):

```bash
python run_evaluation.py \
  --agent heuristic \
  --mode tool_use \
  --trials 1 \
  --start-page "Bradawl" \
  --start-url "https://en.wikipedia.org/wiki/Bradawl"

LLM chat evaluations (article-style):

```bash
# OpenAI example (tool_use returns GAVE UP because chat models cannot browse)
python run_evaluation.py --llm openai:gpt-4o-mini --mode tool_use --trials 1 --start-page "Bradawl" --target-page "Kevin Bacon"

# OpenRouter + Anthropic example
python run_evaluation.py --llm openrouter:anthropic/claude-3-5-sonnet --mode tool_use --trials 1 --start-page "Bradawl" --target-page "Kevin Bacon"
```

Expected summary (approximate):

```
============================================================
Evaluating LLM-openai:gpt-4o-mini in tool_use mode
Running 1 trials...
============================================================

Results Summary for LLM-openai:gpt-4o-mini (tool_use):
Success Rate: 0.0%
Average Score: 15.0
Best Score: 15
Average Path Length: 0.0
Gave Up: 1/1
Cheated: 0/1
Invalid Paths: 0/1

Example Results:
  Trial 1: Bradawl -> GAVE UP
    Score: 15, Success: False
```
```

Notes:
- Wikipedia content evolves; if any hop becomes invalid over time, `validate_path.py` will show alternatives found on the page.
- You can also try `--mode both` to compare conceptual (`no_tool_use`) vs live navigation (`tool_use`) on the same seed.


## Deep Dive: validate_path.py

`validate_path.py` is a precise, step‑by‑step path verifier. It accepts a starting page title and a list of subsequent page titles (including the final target), and then verifies that each next page is present among the prior page’s actual Wikipedia links.

Programmatic API:
```python
from validate_path import validate_wikibench_path

results = validate_wikibench_path(
    start_page="Bradawl",
    path=["Woodworking", "United States", "Hollywood", "Kevin Bacon"],
)

# results = {
#   "valid": True,
#   "errors": [],
#   "step_details": [
#     {"from": "Bradawl", "to": "Woodworking", "valid": True},
#     ...
#   ]
# }
```

CLI:
```bash
python validate_path.py "Bradawl" "Woodworking" "United States" "Hollywood" "Kevin Bacon"
```

What it does under the hood:
- Builds the full path as `[start_page] + path`.
- For each hop, fetches the current page and extracts outbound links using `WikipediaNavigator.get_page_links(url)`.
- Compares the next title case‑insensitively against the set of link titles.
- Records whether the hop is valid; on failure, includes a sample of available links and a human‑readable error.

Output details:
- `valid`: True if all hops are present; False otherwise.
- `errors`: List of hop‑specific error messages.
- `step_details`: Per‑hop diagnostics; for invalid hops, includes `available_links` (subset) or `error`.

Notes:
- Performs live HTTP requests; network access is required.
- Title matching is case‑insensitive in the CLI validator; `wikibench.WikipediaNavigator.is_valid_wikipedia_path` uses case‑sensitive matching by default.
- The validator does not enforce the final target; it verifies links hop‑by‑hop.


## Writing Your Own Agent

To add a custom agent, implement the `AIAgent` interface in `wikibench.py`:

```python
from wikibench import AIAgent, EvaluationMode
from typing import List

class MyAgent(AIAgent):
    def solve_wikibench(self, start_page: str, start_url: str, mode: EvaluationMode) -> List[str]:
        # Return a list of page titles ending (ideally) with the target page
        return ["Some Page", "Another Page", "Kevin Bacon"]  # or another target

    def get_name(self) -> str:
        return "MyAgent"
```

Then evaluate it by importing and registering it in `run_evaluation.py`.


## FAQ / Clarifications

- Does WikiBench always start from a random page?
  - By default, yes. If you do not provide `--start-page` and `--start-url`, the evaluator fetches a random page using `WikipediaNavigator.get_random_page()`. You can fix the start by supplying both flags.

- Is the target always Kevin Bacon?
  - No. Kevin Bacon is the default, but you can set a custom target using `--target-page`. The evaluator uses that for success/cheat checks, and the included agents read the target from `WIKIBENCH_TARGET_PAGE` (which the runner sets for you).

- Does the path validator require Kevin Bacon as the last step?
  - No. `validate_path.py` is a general path validator. It simply checks that each step is reachable from the previous page via a Wikipedia link.


## OpenAI‑Based Agents (Optional)

If you want to experiment with LLM‑driven agents:

```bash
export OPENAI_API_KEY="sk-..."
python -c "import openai; print('OK' if openai.OpenAI(api_key=None) else 'Configured')"
```

- `openai_agent.py`: Conceptual mode (`no_tool_use`) only.

These are examples; they will incur API usage and are not required for the core benchmark.


## Troubleshooting

- HTTP/network errors while validating or in `tool_use` mode:
  - Check connectivity; Wikipedia rate limiting can occasionally cause failures.
  - Re‑run later or reduce `--trials`.
- `--start-page` requires `--start-url`:
  - Provide both so the runner doesn’t fetch the wrong page.
- Paths marked as invalid unexpectedly:
  - Wikipedia content changes over time; a previously valid hop may become invalid if the link disappears or is moved.


## License

This project is intended for educational and research purposes.
