"""
OpenAI Assistants API Agent for WikiBench evaluation
Uses the Assistants API with function calling for tool-use mode
"""

from wikibench import AIAgent, EvaluationMode
from typing import List
import openai
import os
import time
import json


class OpenAIAssistantAgent(AIAgent):
    """Agent that uses OpenAI Assistants API for WikiBench evaluation"""
    
    def __init__(self, model: str = "gpt-4o", api_key: str = None):
        self.model = model
        self.client = openai.OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.assistant = None
        self.thread = None
        
    def _create_assistant(self):
        """Create an assistant with Wikipedia navigation tools"""
        
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_wikipedia_page",
                    "description": "Get the content and links from a Wikipedia page",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_title": {
                                "type": "string",
                                "description": "The title of the Wikipedia page to retrieve"
                            }
                        },
                        "required": ["page_title"]
                    }
                }
            },
            {
                "type": "function", 
                "function": {
                    "name": "navigate_to_page",
                    "description": "Navigate to a Wikipedia page by clicking on a link",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_title": {
                                "type": "string",
                                "description": "The title of the Wikipedia page to navigate to"
                            }
                        },
                        "required": ["page_title"]
                    }
                }
            }
        ]
        
        instructions = """You are a WikiBench agent. Your goal is to navigate from a starting Wikipedia page to Kevin Bacon's Wikipedia page in as few steps as possible.

Rules:
1. You can only move between pages by following actual Wikipedia links
2. Try to find the shortest path possible  
3. Think strategically about connections (geography, professions, time periods, etc.)
4. Keep track of your current location
5. Stop when you reach Kevin Bacon's page

You have these tools available:
- get_wikipedia_page: Get page content and see what links are available
- navigate_to_page: Move to a different Wikipedia page via a link

When you find a path to Kevin Bacon, respond with "PATH COMPLETE: [list of page titles you visited]" """

        self.assistant = self.client.beta.assistants.create(
            name="WikiBench Navigator",
            instructions=instructions,
            model=self.model,
            tools=tools
        )
    
    def _handle_tool_calls(self, tool_calls):
        """Handle tool calls from the assistant"""
        from wikibench import WikipediaNavigator
        navigator = WikipediaNavigator()
        
        tool_outputs = []
        
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            
            try:
                if function_name == "get_wikipedia_page":
                    page_title = arguments["page_title"]
                    url = f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}"
                    
                    # Get page links
                    links = navigator.get_page_links(url)
                    link_titles = [title for title, _ in links[:50]]  # Limit to first 50 links
                    
                    result = {
                        "page_title": page_title,
                        "available_links": link_titles,
                        "total_links": len(links)
                    }
                    
                elif function_name == "navigate_to_page":
                    page_title = arguments["page_title"]
                    result = {
                        "navigated_to": page_title,
                        "status": "success"
                    }
                
                else:
                    result = {"error": f"Unknown function: {function_name}"}
                
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": json.dumps(result)
                })
                
            except Exception as e:
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": json.dumps({"error": str(e)})
                })
        
        return tool_outputs
    
    def solve_wikibench(self, start_page: str, start_url: str, mode: EvaluationMode) -> List[str]:
        if mode == EvaluationMode.NO_TOOL_USE:
            # Use simple completion for conceptual mode
            return self._solve_conceptual(start_page)
        
        # Tool use mode with Assistants API
        return self._solve_with_tools(start_page)
    
    def _solve_conceptual(self, start_page: str) -> List[str]:
        """Solve using simple completion (no tools)"""
        prompt = f"""Find a path from the Wikipedia page "{start_page}" to "Kevin Bacon" by thinking about logical connections.

Starting page: {start_page}
Target: Kevin Bacon

Provide just a list of Wikipedia page titles (one per line) representing your proposed path. Do not include explanations."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=300
            )
            
            # Extract path from response
            lines = response.choices[0].message.content.strip().split('\n')
            path = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith(('Here', 'Path:', '-')):
                    path.append(line)
            
            return path
            
        except Exception as e:
            print(f"Error in conceptual mode: {e}")
            return []
    
    def _solve_with_tools(self, start_page: str) -> List[str]:
        """Solve using Assistants API with tools"""
        try:
            # Create assistant and thread
            if not self.assistant:
                self._create_assistant()
            
            self.thread = self.client.beta.threads.create()
            
            # Send initial message
            message = f"I need to navigate from the Wikipedia page '{start_page}' to Kevin Bacon's page. Please start by getting information about the starting page and then find an efficient path."
            
            self.client.beta.threads.messages.create(
                thread_id=self.thread.id,
                role="user",
                content=message
            )
            
            # Run the assistant
            run = self.client.beta.threads.runs.create(
                thread_id=self.thread.id,
                assistant_id=self.assistant.id
            )
            
            # Monitor the run and handle tool calls
            path = []
            max_iterations = 20  # Prevent infinite loops
            iteration = 0
            
            while iteration < max_iterations:
                # Wait for run to complete or require action
                while run.status in ['queued', 'in_progress']:
                    time.sleep(1)
                    run = self.client.beta.threads.runs.retrieve(
                        thread_id=self.thread.id,
                        run_id=run.id
                    )
                
                if run.status == 'completed':
                    # Get the final response
                    messages = self.client.beta.threads.messages.list(
                        thread_id=self.thread.id
                    )
                    
                    final_message = messages.data[0].content[0].text.value
                    
                    # Extract path from final message
                    if "PATH COMPLETE:" in final_message:
                        path_str = final_message.split("PATH COMPLETE:")[1].strip()
                        # Parse the path - could be various formats
                        import re
                        # Look for page titles in brackets, quotes, or just comma-separated
                        matches = re.findall(r'[\[\("\'](.*?)[\]\)"\'']', path_str)
                        if not matches:
                            # Try comma-separated
                            matches = [p.strip() for p in path_str.split(',') if p.strip()]
                        path = matches
                    
                    break
                
                elif run.status == 'requires_action':
                    # Handle tool calls
                    tool_calls = run.required_action.submit_tool_outputs.tool_calls
                    tool_outputs = self._handle_tool_calls(tool_calls)
                    
                    # Submit tool outputs
                    run = self.client.beta.threads.runs.submit_tool_outputs(
                        thread_id=self.thread.id,
                        run_id=run.id,
                        tool_outputs=tool_outputs
                    )
                    
                    # Track navigation
                    for output in tool_outputs:
                        output_data = json.loads(output["output"])
                        if "navigated_to" in output_data:
                            page = output_data["navigated_to"]
                            if page not in path:
                                path.append(page)
                
                elif run.status in ['failed', 'cancelled', 'expired']:
                    print(f"Run failed with status: {run.status}")
                    break
                
                iteration += 1
            
            return path
            
        except Exception as e:
            print(f"Error in tool mode: {e}")
            return []
        
        finally:
            # Clean up
            if self.thread:
                try:
                    self.client.beta.threads.delete(self.thread.id)
                except:
                    pass
    
    def get_name(self) -> str:
        return f"OpenAI-Assistant-{self.model}"
    
    def __del__(self):
        """Clean up assistant when done"""
        if self.assistant:
            try:
                self.client.beta.assistants.delete(self.assistant.id)
            except:
                pass


if __name__ == "__main__":
    # Test the assistant agent
    agent = OpenAIAssistantAgent("gpt-4o")
    
    # Test both modes
    start_page = "bradawl"
    start_url = "https://en.wikipedia.org/wiki/Bradawl"
    
    print("Testing conceptual mode...")
    path_conceptual = agent.solve_wikibench(start_page, start_url, EvaluationMode.NO_TOOL_USE)
    print(f"Conceptual path: {path_conceptual}")
    
    print("\nTesting tool-use mode...")
    path_tools = agent.solve_wikibench(start_page, start_url, EvaluationMode.TOOL_USE)
    print(f"Tool-use path: {path_tools}")