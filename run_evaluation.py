#!/usr/bin/env python3
"""
WikiBench Evaluation Runner

Example usage:
    python run_evaluation.py --agent random --mode tool_use --trials 5
    python run_evaluation.py --agent heuristic --mode both --trials 10
    python run_evaluation.py --all-agents --mode tool_use --trials 3

Custom target example:
    python run_evaluation.py --agent heuristic --mode tool_use --trials 3 \
        --target-page "Barack Obama"
"""

import argparse
import os
from wikibench import WikiBenchEvaluator, EvaluationMode
from example_agents import (
    RandomAgent, GreedyActorAgent, HeuristicAgent,
    CheatAgent, GiveUpAgent
)


def main():
    parser = argparse.ArgumentParser(description="Run WikiBench evaluations")
    parser.add_argument(
        "--agent",
        choices=["random", "greedy", "heuristic", "cheat", "giveup"],
        help="Which agent to evaluate"
    )
    parser.add_argument(
        "--all-agents",
        action="store_true",
        help="Evaluate all available agents"
    )
    parser.add_argument(
        "--mode",
        choices=["no_tool_use", "tool_use", "both"],
        default="tool_use",
        help="Evaluation mode"
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=5,
        help="Number of trials per agent/mode combination"
    )
    parser.add_argument(
        "--output-dir",
        default="results",
        help="Directory to save results"
    )
    parser.add_argument(
        "--start-page",
        help="Specific starting page (optional, otherwise random)"
    )
    parser.add_argument(
        "--start-url",
        help="Specific starting URL (if omitted with --start-page, it will be derived)"
    )
    parser.add_argument(
        "--target-page",
        default="Kevin Bacon",
        help="Target page title (default: Kevin Bacon)"
    )
    parser.add_argument(
        "--target-url",
        help="Target page URL (optional; derived from title if omitted)"
    )
    parser.add_argument(
        "--llm",
        help="LLM spec, e.g., 'openai:gpt-4o-mini'. Cannot be combined with --agent/--all-agents."
    )

    args = parser.parse_args()

    # Validate arguments
    if not any([args.agent, args.all_agents, args.llm]):
        parser.error("Must specify one of: --agent, --all-agents, or --llm")
    if sum(bool(x) for x in [args.agent, args.all_agents, args.llm]) > 1:
        parser.error("Use only one of: --agent, --all-agents, or --llm")


    # Make target available to example agents via env var
    os.environ["WIKIBENCH_TARGET_PAGE"] = args.target_page
    if args.target_url:
        os.environ["WIKIBENCH_TARGET_URL"] = args.target_url

    # Create evaluator with target configuration
    evaluator = WikiBenchEvaluator(target_page=args.target_page, target_url=args.target_url)

    # Define agents
    agents = {
        "random": RandomAgent(),
        "greedy": GreedyActorAgent(),
        "heuristic": HeuristicAgent(),
        "cheat": CheatAgent(),
        "giveup": GiveUpAgent(),
    }

    # Select agents to evaluate
    if args.all_agents:
        agents_to_evaluate = agents
    elif args.llm:
        # Parse LLM spec: provider:model
        try:
            provider, model = args.llm.split(":", 1)
        except ValueError:
            parser.error("--llm must be in the form 'provider:model', e.g., 'openai:gpt-4o-mini'")
        provider = provider.strip()
        model = model.strip()

        from llm_agents import LLMChatAgent
        agent_llm = LLMChatAgent(provider=provider, model=model)
        agents_to_evaluate = {agent_llm.get_name(): agent_llm}
    else:
        agents_to_evaluate = {args.agent: agents[args.agent]}

    # Select evaluation modes
    if args.mode == "both":
        modes = [EvaluationMode.NO_TOOL_USE, EvaluationMode.TOOL_USE]
    else:
        modes = [EvaluationMode(args.mode)]

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Run evaluations
    for agent_name, agent in agents_to_evaluate.items():
        for mode in modes:
            print(f"\n{'='*60}")
            print(f"Evaluating {agent_name} in {mode.value} mode")
            print(f"Running {args.trials} trials...")
            print(f"{'='*60}")

            if args.start_page:
                # Single evaluation with specified starting page
                start_url = args.start_url or f"https://en.wikipedia.org/wiki/{args.start_page.replace(' ', '_')}"
                result = evaluator.run_single_evaluation(
                    agent, mode, args.start_page, start_url
                )
                results = [result]
            else:
                # Multiple evaluations with random starting pages
                results = evaluator.run_evaluation_suite(agent, mode, args.trials)

            # Generate and save report
            report = evaluator.generate_report(results, agent_name)

            # Print summary
            print(f"\nResults Summary for {agent_name} ({mode.value}):")
            print(f"Success Rate: {report['success_rate']:.1f}%")
            print(f"Average Score: {report['average_score']:.1f}")
            print(f"Best Score: {report['best_score']}")
            print(f"Average Path Length: {report['average_path_length']:.1f}")
            print(f"Gave Up: {report['gave_up_count']}/{report['total_trials']}")
            print(f"Cheated: {report['cheated_count']}/{report['total_trials']}")
            print(f"Invalid Paths: {report['invalid_path_count']}/{report['total_trials']}")

            # Show some example results
            print(f"\nExample Results:")
            for i, r in enumerate(results[:3]):  # Show first 3 results
                path_str = ' -> '.join(r.path) if r.path else 'GAVE UP'
                print(f"  Trial {i+1}: {r.start_page} -> {path_str}")
                print(f"    Score: {r.score}, Success: {r.success}")
                # Print the LLM's raw response when available
                if getattr(r, 'raw_response', None):
                    raw = r.raw_response.strip()
                    preview = raw if len(raw) <= 800 else (raw[:800] + "... [truncated]")
                    print("    LLM Response:\n" + "\n".join(["      " + line for line in preview.splitlines()]))

            # Save detailed results
            safe_agent_name = agent_name.replace('/', '_')
            filename = f"{args.output_dir}/{safe_agent_name}_{mode.value}_results.json"
            evaluator.save_results(report, filename)
            print(f"\nDetailed results saved to: {filename}")

    print(f"\nAll evaluations completed. Results saved in {args.output_dir}/")


if __name__ == "__main__":
    main()
