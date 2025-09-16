"""
WikiBench: A benchmark for testing AI agents' ability to navigate from random Wikipedia pages to Kevin Bacon's page.

Based on the article: https://1thousandfaces.substack.com/p/wikibench-76-of-sota-models-fail
"""

import requests
import re
from typing import List, Dict, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import time
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import json
from abc import ABC, abstractmethod


class EvaluationMode(Enum):
    NO_TOOL_USE = "no_tool_use"  # Predict path conceptually
    TOOL_USE = "tool_use"        # Actually navigate Wikipedia


@dataclass
class WikiBenchResult:
    """Result of a single WikiBench evaluation"""
    start_page: str
    start_url: str
    target_page: str = "Kevin Bacon"
    target_url: str = "https://en.wikipedia.org/wiki/Kevin_Bacon"
    path: List[str] = None
    score: int = 0
    success: bool = False
    gave_up: bool = False
    cheated: bool = False
    invalid_path: bool = False
    creative_connections: int = 0
    time_taken: float = 0.0
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.path is None:
            self.path = []


class WikipediaNavigator:
    """Utility class for Wikipedia navigation and validation"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'WikiBench/1.0 (Educational Research Tool)'
        })
    
    def get_random_page(self) -> Tuple[str, str]:
        """Get a random Wikipedia page title and URL"""
        try:
            response = self.session.get("https://en.wikipedia.org/wiki/Special:Random")
            response.raise_for_status()
            
            # Get the final URL after redirect
            final_url = response.url
            title = final_url.split('/wiki/')[-1].replace('_', ' ')
            
            return title, final_url
        except Exception as e:
            raise Exception(f"Failed to get random page: {e}")
    
    def get_page_links(self, url: str) -> List[Tuple[str, str]]:
        """Extract all Wikipedia links from a page"""
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            content = soup.find('div', {'id': 'mw-content-text'})
            
            if not content:
                return []
            
            links = []
            for link in content.find_all('a', href=True):
                href = link['href']
                if href.startswith('/wiki/') and ':' not in href and '#' not in href:
                    full_url = urljoin("https://en.wikipedia.org", href)
                    title = href.split('/wiki/')[-1].replace('_', ' ')
                    links.append((title, full_url))
            
            return links
        except Exception as e:
            raise Exception(f"Failed to get page links: {e}")
    
    def is_valid_wikipedia_path(self, path: List[str]) -> bool:
        """Validate that a path represents valid Wikipedia page transitions"""
        if not path:
            return False
        
        try:
            for i in range(len(path) - 1):
                current_url = f"https://en.wikipedia.org/wiki/{path[i].replace(' ', '_')}"
                next_page = path[i + 1]
                
                links = self.get_page_links(current_url)
                link_titles = [title for title, _ in links]
                
                if next_page not in link_titles:
                    return False
            
            return True
        except Exception:
            return False
    
    def check_if_reached_target(self, current_page: str, target_page: str = "Kevin Bacon") -> bool:
        """Check if the current page is the target page"""
        return current_page.lower() == target_page.lower()


class WikiBenchScorer:
    """Scoring system for WikiBench evaluations"""
    
    BASE_SCORE = 0
    INVALID_PATH_PENALTY = 10
    GAVE_UP_PENALTY = 15
    CHEATING_PENALTY = 20
    CREATIVE_CONNECTION_BONUS = -1
    
    @classmethod
    def calculate_score(cls, result: WikiBenchResult) -> int:
        """Calculate the final score for a WikiBench result"""
        score = cls.BASE_SCORE + len(result.path)  # Base score is path length
        
        if result.invalid_path:
            score += cls.INVALID_PATH_PENALTY
        
        if result.gave_up:
            score += cls.GAVE_UP_PENALTY
        
        if result.cheated:
            score += cls.CHEATING_PENALTY
        
        score += result.creative_connections * cls.CREATIVE_CONNECTION_BONUS
        
        return max(0, score)  # Ensure non-negative score


class AIAgent(ABC):
    """Abstract base class for AI agents to be evaluated"""
    
    @abstractmethod
    def solve_wikibench(self, start_page: str, start_url: str, mode: EvaluationMode) -> List[str]:
        """
        Solve a WikiBench challenge
        
        Args:
            start_page: Title of the starting Wikipedia page
            start_url: URL of the starting Wikipedia page  
            mode: Evaluation mode (tool use or no tool use)
            
        Returns:
            List of page titles representing the path to Kevin Bacon
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Return the name of this AI agent"""
        pass


class WikiBenchEvaluator:
    """Main evaluation harness for WikiBench"""
    
    def __init__(self):
        self.navigator = WikipediaNavigator()
        self.scorer = WikiBenchScorer()
    
    def run_single_evaluation(self, agent: AIAgent, mode: EvaluationMode, 
                            start_page: Optional[str] = None, 
                            start_url: Optional[str] = None) -> WikiBenchResult:
        """Run a single WikiBench evaluation"""
        
        # Get random starting page if not provided
        if start_page is None or start_url is None:
            start_page, start_url = self.navigator.get_random_page()
        
        result = WikiBenchResult(
            start_page=start_page,
            start_url=start_url
        )
        
        try:
            start_time = time.time()
            
            # Get path from agent
            path = agent.solve_wikibench(start_page, start_url, mode)
            
            result.time_taken = time.time() - start_time
            result.path = path if path else []
            
            # Check for cheating (direct jump to Kevin Bacon without valid path)
            if len(result.path) == 1 and result.path[0] == "Kevin Bacon":
                result.cheated = True
            
            # Check if gave up (empty path or explicit indication)
            if not result.path:
                result.gave_up = True
            
            # Validate path for tool use mode
            if mode == EvaluationMode.TOOL_USE and result.path:
                full_path = [start_page] + result.path
                result.invalid_path = not self.navigator.is_valid_wikipedia_path(full_path)
            
            # Check success
            if result.path and not result.gave_up and not result.cheated:
                result.success = self.navigator.check_if_reached_target(result.path[-1])
            
            # Calculate score
            result.score = self.scorer.calculate_score(result)
            
        except Exception as e:
            result.error_message = str(e)
            result.gave_up = True
            result.score = self.scorer.calculate_score(result)
        
        return result
    
    def run_evaluation_suite(self, agent: AIAgent, mode: EvaluationMode, 
                           num_trials: int = 10) -> List[WikiBenchResult]:
        """Run multiple WikiBench evaluations"""
        results = []
        
        for i in range(num_trials):
            print(f"Running trial {i+1}/{num_trials} for {agent.get_name()}")
            result = self.run_single_evaluation(agent, mode)
            results.append(result)
            
            # Small delay to be respectful to Wikipedia
            time.sleep(1)
        
        return results
    
    def generate_report(self, results: List[WikiBenchResult], agent_name: str) -> Dict:
        """Generate evaluation report"""
        if not results:
            return {}
        
        total_trials = len(results)
        successful_trials = sum(1 for r in results if r.success)
        gave_up_count = sum(1 for r in results if r.gave_up)
        cheated_count = sum(1 for r in results if r.cheated)
        invalid_path_count = sum(1 for r in results if r.invalid_path)
        
        scores = [r.score for r in results]
        path_lengths = [len(r.path) for r in results if r.path]
        
        report = {
            "agent_name": agent_name,
            "total_trials": total_trials,
            "successful_trials": successful_trials,
            "success_rate": successful_trials / total_trials * 100,
            "gave_up_count": gave_up_count,
            "cheated_count": cheated_count,
            "invalid_path_count": invalid_path_count,
            "average_score": sum(scores) / len(scores),
            "best_score": min(scores),
            "worst_score": max(scores),
            "average_path_length": sum(path_lengths) / len(path_lengths) if path_lengths else 0,
            "results": [
                {
                    "start_page": r.start_page,
                    "path": r.path,
                    "score": r.score,
                    "success": r.success,
                    "gave_up": r.gave_up,
                    "cheated": r.cheated,
                    "invalid_path": r.invalid_path,
                    "time_taken": r.time_taken,
                    "error_message": r.error_message
                }
                for r in results
            ]
        }
        
        return report
    
    def save_results(self, report: Dict, filename: str):
        """Save evaluation results to JSON file"""
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)


if __name__ == "__main__":
    # Example usage will be shown in the example file
    print("WikiBench evaluation harness loaded successfully!")