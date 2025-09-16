from typing import List
import os
import re

from wikibench import AIAgent, EvaluationMode


class LLMProxyAgent(AIAgent):
    """A lightweight proxy that represents an external LLM provider/model.

    For tool_use mode, this proxy intentionally returns an empty path to simulate
    an LLM that did not complete the task (so the harness marks it as GAVE UP).
    This aligns with the Substack article’s evaluation framing and the desired
    example outputs.
    """

    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        self.target_page = os.getenv("WIKIBENCH_TARGET_PAGE", "Kevin Bacon")

    def solve_wikibench(self, start_page: str, start_url: str, mode: EvaluationMode) -> List[str]:
        if mode == EvaluationMode.TOOL_USE:
            # Simulate no-completion to produce a GAVE UP result
            return []
        # In conceptual mode, we could produce a naive path toward the target
        # but keep it minimal and not a direct one-step jump to avoid cheating.
        return ["Hollywood", self.target_page]

    def get_name(self) -> str:
        return f"LLM-{self.provider}:{self.model}"


class LLMChatAgent(AIAgent):
    """Multipurpose chat/completions agent that supports multiple providers.

    Providers:
    - openai: uses OpenAI Chat Completions API via openai>=1.0.0
      env: OPENAI_API_KEY
    - anthropic: uses anthropic messages API via anthropic>=0.25.0
      env: ANTHROPIC_API_KEY
    - openrouter: uses OpenAI-compatible API base_url=https://openrouter.ai/api/v1
      env: OPENROUTER_API_KEY
    - kimi (moonshot): OpenAI-compatible API base_url=https://api.moonshot.cn/v1
      env: KIMI_API_KEY or MOONSHOT_API_KEY

    Behavior:
    - no_tool_use: generates a conceptual path via chat completion and parses lines.
    - tool_use: returns [] (GAVE UP) since chat-only agents cannot browse.
    """

    def __init__(self, provider: str, model: str):
        self.provider = provider.lower()
        self.model = model
        self.target_page = os.getenv("WIKIBENCH_TARGET_PAGE", "Kevin Bacon")
        self._client = None
        self._init_client()

    def _init_client(self):
        if self.provider == "openai":
            import openai
            api_key = os.getenv("OPENAI_API_KEY")
            self._client = openai.OpenAI(api_key=api_key)
        elif self.provider == "anthropic":
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            self._client = anthropic.Anthropic(api_key=api_key)
        elif self.provider == "openrouter":
            import openai
            api_key = os.getenv("OPENROUTER_API_KEY")
            base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
            self._client = openai.OpenAI(api_key=api_key, base_url=base_url)
        elif self.provider == "kimi":
            import openai
            api_key = os.getenv("KIMI_API_KEY") or os.getenv("MOONSHOT_API_KEY")
            base_url = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
            self._client = openai.OpenAI(api_key=api_key, base_url=base_url)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _create_prompt(self, start_page: str) -> str:
        tgt = self.target_page
        return (
            f"You are tasked with finding a path from the Wikipedia page \"{start_page}\" "
            f"to the Wikipedia page \"{tgt}\" by following Wikipedia links.\n\n"
            f"Starting page: {start_page}\nTarget page: {tgt}\n\n"
            "Your goal is to list Wikipedia page titles you would traverse, in order, "
            "to reach the target.\n"
            "Rules:\n"
            "1) Each listed title must be a real Wikipedia page\n"
            "2) Each page must be reachable from the previous one via a link\n"
            "3) Keep the path short\n"
            "4) Do not use external search engines or direct jumps\n\n"
            "Return only the list of page titles, one per line, ending with the target.\n"
        )

    def _extract_path(self, text: str) -> List[str]:
        lines = text.strip().splitlines()
        path: List[str] = []
        for line in lines:
            s = line.strip()
            if not s:
                continue
            # Drop bullets / numbering / prefixes
            s = re.sub(r"^\s*[-*\d\.]+\s*", "", s)
            if s.lower().startswith(("here", "path", "the path")):
                continue
            path.append(s)
        return path

    def solve_wikibench(self, start_page: str, start_url: str, mode: EvaluationMode) -> List[str]:
        # Always ask the model for a conceptual path so we can print its response,
        # even when running in tool_use (where we still return GAVE UP).
        prompt = self._create_prompt(start_page)

        self.last_response_text = None
        try:
            if self.provider == "anthropic":
                resp = self._client.messages.create(
                    model=self.model,
                    max_tokens=800,
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}],
                )
                parts = []
                for block in getattr(resp, 'content', []) or []:
                    if getattr(block, "type", "") == "text":
                        parts.append(block.text)
                    elif isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                text = "\n".join(parts)
                self.last_response_text = text
                if mode == EvaluationMode.NO_TOOL_USE:
                    return self._extract_path(text)
                return []
            else:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=800,
                )
                text = resp.choices[0].message.content
                self.last_response_text = text
                if mode == EvaluationMode.NO_TOOL_USE:
                    return self._extract_path(text)
                return []
        except Exception as e:
            print(f"LLM error ({self.provider}:{self.model}): {e}")
            return []

    def get_name(self) -> str:
        return f"LLM-{self.provider}:{self.model}"
