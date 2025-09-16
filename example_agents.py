"""
Example AI agent implementations for WikiBench evaluation.
These demonstrate how to implement the AIAgent interface.
"""

from wikibench import AIAgent, EvaluationMode, WikipediaNavigator
from typing import List
import random
import os


class RandomAgent(AIAgent):
    """An agent that makes random moves - useful as a baseline"""
    
    def __init__(self, max_steps: int = 10):
        self.max_steps = max_steps
        self.navigator = WikipediaNavigator()
        self.target_page = os.getenv("WIKIBENCH_TARGET_PAGE", "Kevin Bacon")
    
    def solve_wikibench(self, start_page: str, start_url: str, mode: EvaluationMode) -> List[str]:
        if mode == EvaluationMode.NO_TOOL_USE:
            # Just return a random conceptual path
            possible_connections = [
                "Actor", "Film", "Hollywood", self.target_page,
                "Celebrity", "Movie", "Entertainment", self.target_page
            ]
            path_length = random.randint(2, 6)
            return random.choices(possible_connections, k=path_length)
        
        else:  # TOOL_USE mode
            current_url = start_url
            path = []
            
            for _ in range(self.max_steps):
                try:
                    links = self.navigator.get_page_links(current_url)
                    if not links:
                        break
                    
                    # Check if target page is in the links
                    for title, url in links:
                        if self.target_page in title:
                            path.append(self.target_page)
                            return path
                    
                    # Otherwise pick a random link
                    title, url = random.choice(links)
                    path.append(title)
                    current_url = url
                    
                except Exception:
                    break
            
            return path
    
    def get_name(self) -> str:
        return "RandomAgent"


class GreedyActorAgent(AIAgent):
    """An agent that greedily searches for actor/film-related pages"""
    
    def __init__(self, max_steps: int = 15):
        self.max_steps = max_steps
        self.navigator = WikipediaNavigator()
        self.target_page = os.getenv("WIKIBENCH_TARGET_PAGE", "Kevin Bacon")
        self.actor_keywords = [
            "actor", "actress", "film", "movie", "cinema", "hollywood", 
            "director", "producer", "celebrity", "star", "entertainment",
            "television", "tv", "show", "series", "drama", "comedy"
        ]
    
    def solve_wikibench(self, start_page: str, start_url: str, mode: EvaluationMode) -> List[str]:
        if mode == EvaluationMode.NO_TOOL_USE:
            # Conceptual path toward entertainment/acting
            return [
                "Entertainment industry", 
                "American actor", 
                "Hollywood",
                self.target_page
            ]
        
        else:  # TOOL_USE mode
            current_url = start_url
            path = []
            
            for step in range(self.max_steps):
                try:
                    links = self.navigator.get_page_links(current_url)
                    if not links:
                        break
                    
                    # Check if target page is directly available
                    for title, url in links:
                        if self.target_page in title:
                            path.append(self.target_page)
                            return path
                    
                    # Score links based on actor/entertainment relevance
                    scored_links = []
                    for title, url in links:
                        score = 0
                        title_lower = title.lower()
                        
                        for keyword in self.actor_keywords:
                            if keyword in title_lower:
                                score += 1
                        
                        # Bonus for American/English content (often relevant to entertainment topics)
                        if any(word in title_lower for word in ["american", "english", "british", "united states"]):
                            score += 2
                        
                        scored_links.append((score, title, url))
                    
                    # Sort by score and pick the best
                    scored_links.sort(reverse=True)
                    
                    if scored_links and scored_links[0][0] > 0:
                        _, title, url = scored_links[0]
                    else:
                        # If no good matches, pick randomly from top 10
                        top_links = links[:10] if len(links) >= 10 else links
                        title, url = random.choice(top_links)
                    
                    path.append(title)
                    current_url = url
                    
                except Exception:
                    break
            
            return path
    
    def get_name(self) -> str:
        return "GreedyActorAgent"


class HeuristicAgent(AIAgent):
    """An agent that uses multiple heuristics to navigate toward the target page"""
    
    def __init__(self, max_steps: int = 20):
        self.max_steps = max_steps
        self.navigator = WikipediaNavigator()
        self.visited_pages = set()
        self.target_page = os.getenv("WIKIBENCH_TARGET_PAGE", "Kevin Bacon")
    
    def solve_wikibench(self, start_page: str, start_url: str, mode: EvaluationMode) -> List[str]:
        self.visited_pages = {start_page}  # Reset for each evaluation
        
        if mode == EvaluationMode.NO_TOOL_USE:
            # Strategic conceptual path
            return [
                "United States",
                "American cinema", 
                "Hollywood",
                "American actor",
                self.target_page
            ]
        
        else:  # TOOL_USE mode
            current_url = start_url
            path = []
            
            for step in range(self.max_steps):
                try:
                    links = self.navigator.get_page_links(current_url)
                    if not links:
                        break
                    
                    # Check if target page is directly available
                    for title, url in links:
                        if self.target_page in title:
                            path.append(self.target_page)
                            return path
                    
                    # Apply heuristics to score links
                    best_link = self._select_best_link(links, step)
                    
                    if best_link:
                        title, url = best_link
                        if title not in self.visited_pages:
                            path.append(title)
                            current_url = url
                            self.visited_pages.add(title)
                        else:
                            # If we've been here before, try a random unvisited link
                            unvisited = [(t, u) for t, u in links if t not in self.visited_pages]
                            if unvisited:
                                title, url = random.choice(unvisited)
                                path.append(title)
                                current_url = url
                                self.visited_pages.add(title)
                            else:
                                break
                    else:
                        break
                        
                except Exception:
                    break
            
            return path
    
    def _select_best_link(self, links: List[tuple], step: int) -> tuple:
        """Select the best link using multiple heuristics"""
        
        # High-value target terms (in order of preference)
        target_lower = self.target_page.lower()
        target_tail = self.target_page.split()[-1].lower()
        high_value_terms = [
            [target_lower, target_tail],  # Direct target (full name + last token)
            ["actor", "actress", "performer"],  # Acting profession
            ["film", "movie", "cinema"],  # Film industry
            ["american", "united states", "usa"],  # Geographic relevance
            ["hollywood", "entertainment"],  # Industry centers
            ["television", "tv", "show"],  # Related media
            ["celebrity", "star", "famous"],  # Fame-related
        ]
        
        best_score = -1
        best_link = None
        
        for title, url in links:
            title_lower = title.lower()
            score = 0
            
            # Score based on high-value terms (higher index = higher priority)
            for i, term_group in enumerate(high_value_terms):
                for term in term_group:
                    if term in title_lower:
                        score += (len(high_value_terms) - i) * 10
                        break
            
            # Bonus for specific patterns
            if "born" in title_lower and ("19" in title or "20" in title):
                score += 5  # Likely a person's biography
            
            if any(word in title_lower for word in ["list of", "category:", "disambiguation"]):
                score -= 5  # Avoid meta pages
            
            # Early in search, prefer broader topics; later prefer more specific
            if step < 5:
                if any(word in title_lower for word in ["united states", "american", "film", "actor"]):
                    score += 3
            else:
                if any(word in title_lower for word in ["kevin", "bacon", "actor", "film"]):
                    score += 5
            
            if score > best_score:
                best_score = score
                best_link = (title, url)
        
        return best_link
    
    def get_name(self) -> str:
        return "HeuristicAgent"


class CheatAgent(AIAgent):
    """An agent that attempts to cheat by jumping directly to the target page"""
    
    def solve_wikibench(self, start_page: str, start_url: str, mode: EvaluationMode) -> List[str]:
        # Always tries to cheat by going directly to the target page
        target_page = os.getenv("WIKIBENCH_TARGET_PAGE", "Kevin Bacon")
        return [target_page]
    
    def get_name(self) -> str:
        return "CheatAgent"


class GiveUpAgent(AIAgent):
    """An agent that immediately gives up - useful for testing penalty system"""
    
    def solve_wikibench(self, start_page: str, start_url: str, mode: EvaluationMode) -> List[str]:
        # Always gives up
        return []
    
    def get_name(self) -> str:
        return "GiveUpAgent"
