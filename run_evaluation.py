#!/usr/bin/env python3
"""
WikiBench Evaluation Runner

Example usage:
    python run_evaluation.py --agent random --mode tool_use --trials 5
    python run_evaluation.py --agent heuristic --mode both --trials 10
    python run_evaluation.py --all-agents --mode tool_use --trials 3
"""

import argparse
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
        help="Specific starting URL (required if start-page is provided)"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.agent and not args.all_agents:
        parser.error("Must specify either --agent or --all-agents")
    
    if args.start_page and not args.start_url:
        parser.error("--start-url is required when --start-page is provided")
    
    # Create evaluator
    evaluator = WikiBenchEvaluator()
    
    # Define agents
    agents = {
        "random": RandomAgent(),
        "greedy": GreedyActorAgent(), 
        "heuristic": HeuristicAgent(),
        "cheat": CheatAgent(),
        "giveup": GiveUpAgent()
    }
    
    # Select agents to evaluate
    if args.all_agents:
        agents_to_evaluate = agents
    else:
        agents_to_evaluate = {args.agent: agents[args.agent]}
    
    # Select evaluation modes
    if args.mode == "both":
        modes = [EvaluationMode.NO_TOOL_USE, EvaluationMode.TOOL_USE]
    else:
        modes = [EvaluationMode(args.mode)]
    
    # Create output directory
    import os
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Run evaluations
    for agent_name, agent in agents_to_evaluate.items():
        for mode in modes:
            print(f"\n{'='*60}")
            print(f"Evaluating {agent_name} in {mode.value} mode")
            print(f"Running {args.trials} trials...")
            print(f"{'='*60}")
            
            if args.start_page and args.start_url:
                # Single evaluation with specified starting page
                result = evaluator.run_single_evaluation(
                    agent, mode, args.start_page, args.start_url
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
            for i, result in enumerate(results[:3]):  # Show first 3 results
                print(f"  Trial {i+1}: {result['start_page']} -> {' -> '.join(result['path']) if result['path'] else 'GAVE UP'}")
                print(f"    Score: {result['score']}, Success: {result['success']}")
            
            # Save detailed results
            filename = f"{args.output_dir}/{agent_name}_{mode.value}_results.json"
            evaluator.save_results(report, filename)
            print(f"\nDetailed results saved to: {filename}")
    
    print(f"\nAll evaluations completed. Results saved in {args.output_dir}/")


if __name__ == "__main__":
    main()