"""
OpenAI GPT Agent for WikiBench evaluation
"""

from wikibench import AIAgent, EvaluationMode
from typing import List
import openai
import os


class OpenAIAgent(AIAgent):
    """Agent that uses OpenAI GPT models for WikiBench evaluation"""
    
    def __init__(self, model: str = "gpt-4", api_key: str = None):
        self.model = model
        self.client = openai.OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.target_page = os.getenv("WIKIBENCH_TARGET_PAGE", "Kevin Bacon")
    
    def solve_wikibench(self, start_page: str, start_url: str, mode: EvaluationMode) -> List[str]:
        if mode == EvaluationMode.TOOL_USE:
            raise NotImplementedError("Tool use mode not implemented for OpenAI agent")
        
        # Create the prompt for no-tool-use mode
        prompt = self._create_prompt(start_page)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # Low temperature for more consistent results
                max_tokens=500
            )
            
            # Extract path from response
            path = self._extract_path_from_response(response.choices[0].message.content)
            return path
            
        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            return []
    
    def _create_prompt(self, start_page: str) -> str:
        """Create the prompt for the WikiBench task"""
        target = self.target_page
        return f"""You are tasked with finding a path from the Wikipedia page "{start_page}" to the Wikipedia page "{target}" by following Wikipedia links.

Starting page: {start_page}
Target page: {target}

Your goal is to identify a sequence of Wikipedia page titles that would allow you to navigate from the starting page to {target}'s page by clicking on links. You should think about logical connections between topics.

Important rules:
1. Each page in your path must be a real Wikipedia page
2. Each page must be reachable from the previous page via a Wikipedia link
3. Try to find the shortest path possible
4. Do not use external search engines or direct jumps
5. Think about conceptual connections (geography, profession, time period, etc.)

Please provide your answer as a simple list of Wikipedia page titles, one per line, representing the path from "{start_page}" to "{target}". Do not include the starting page or explanations, just the intermediate pages and the final target.

Example format:
Page 1
Page 2  
Page 3
{target}"""
    
    def _extract_path_from_response(self, response_text: str) -> List[str]:
        """Extract the path from the model's response"""
        lines = response_text.strip().split('\n')
        path = []
        
        for line in lines:
            line = line.strip()
            # Skip empty lines and common prefixes
            if not line or line.startswith(('Here', 'The path', 'Path:', '-', '*', '1.', '2.')):
                continue
            
            # Remove numbering if present
            import re
            line = re.sub(r'^\d+\.\s*', '', line)
            line = re.sub(r'^[-*]\s*', '', line)
            
            if line:
                path.append(line)
        
        return path
    
    def get_name(self) -> str:
        return f"OpenAI-{self.model}"


if __name__ == "__main__":
    # Example: Test the bradawl → target path from the article
    
    # You'll need to set your OpenAI API key
    # export OPENAI_API_KEY="your-api-key-here"
    
    agent = OpenAIAgent("gpt-4")
    
    # Test with the example from the article
    start_page = "bradawl"
    start_url = "https://en.wikipedia.org/wiki/Bradawl"
    
    target = agent.target_page
    print(f"Testing path from '{start_page}' to '{target}'")
    path = agent.solve_wikibench(start_page, start_url, EvaluationMode.NO_TOOL_USE)
    
    print(f"\nProposed path:")
    print(f"{start_page} →")
    for page in path:
        print(f"  {page} →")
    
    # Now validate the path
    from wikibench import WikiBenchEvaluator
    
    evaluator = WikiBenchEvaluator()
    result = evaluator.run_single_evaluation(
        agent, 
        EvaluationMode.NO_TOOL_USE, 
        start_page, 
        start_url
    )
    
    print(f"\nEvaluation Result:")
    print(f"Score: {result.score}")
    print(f"Success: {result.success}")
    print(f"Path length: {len(result.path)}")
    print(f"Gave up: {result.gave_up}")
    print(f"Cheated: {result.cheated}")
