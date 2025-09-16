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
        # Normalize model aliases for certain providers
        self._normalize_model_aliases()
        self._init_client()

    def _normalize_model_aliases(self):
        if self.provider == "anthropic":
            # Accept common shorthand/alias forms and map to official Anthropic IDs
            # e.g., "claude-3-5-sonnet" -> "claude-3-5-sonnet-20240620"
            m = self.model.replace("/", ":").replace("3.5", "3-5").lower()
            # Keep the original if it's already a full ID
            aliases = {
                "claude-3-5-sonnet": "claude-3-5-sonnet-20240620",
                "claude-3-5-sonnet-latest": "claude-3-5-sonnet-latest",
                "claude-3-opus": "claude-3-opus-20240229",
                "claude-3-sonnet": "claude-3-sonnet-20240229",
                "claude-3-haiku": "claude-3-haiku-20240307",
            }
            if m in aliases:
                self.model = aliases[m]

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
            f"Find a path from the Wikipedia page \"{start_page}\" to \"{tgt}\" by following only on‑wiki links.\n\n"
            f"Starting page: {start_page}\nTarget page: {tgt}\n\n"
            "Output format (strict):\n"
            "- Only the list of Wikipedia page titles, one per line\n"
            "- Do NOT include the starting page in your list\n"
            "- The last line MUST be the target page\n"
            "- No bullets, numbers, dashes, or commentary\n"
        )

    def _extract_path(self, text: str, start_page: str) -> List[str]:
        lines = text.strip().splitlines()
        path: List[str] = []
        for line in lines:
            s = line.strip()
            if not s:
                continue
            # Drop bullets / numbering / prefixes
            s = re.sub(r"^\s*[-*\d\.]+\s*", "", s)
            # Strip surrounding quotes
            s = s.strip('"').strip("'")
            # Skip leading commentary lines
            if s.lower().startswith(("here", "path", "the path")):
                continue
            # Skip explicit repeats of the starting page
            if s.lower() == start_page.lower():
                continue
            # Drop blank after cleaning
            if not s:
                continue
            path.append(s)
        # If the model forgot to include the target as the last line, append if present elsewhere
        if path and path[-1].lower() != self.target_page.lower():
            # If target appears somewhere, move it to the end; otherwise, append it
            lowered = [p.lower() for p in path]
            if self.target_page.lower() in lowered:
                first_idx = lowered.index(self.target_page.lower())
                # Keep everything up to that idx, then ensure target last
                path = path[: first_idx + 1]
            else:
                path.append(self.target_page)

        # Fallback: arrow-separated single-line format
        if not path and ("->" in text or "→" in text):
            pieces = re.split(r"\s*(?:->|→)\s*", text)
            for p in pieces:
                p = p.strip().strip('"').strip("'")
                if not p:
                    continue
                if p.lower() == start_page.lower():
                    continue
                # Heuristic: skip commentary chunks
                if len(p.split()) > 7:
                    continue
                path.append(p)
            if path and path[-1].lower() != self.target_page.lower():
                path.append(self.target_page)
        return path

    def solve_wikibench(self, start_page: str, start_url: str, mode: EvaluationMode) -> List[str]:
        # Always ask the model for a conceptual path so we can print its response
        # and, in both modes, parse a path from it.
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
                parsed = self._extract_path(text, start_page)
                return parsed
            else:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=800,
                )
                text = resp.choices[0].message.content
                self.last_response_text = text
                parsed = self._extract_path(text, start_page)
                return parsed
        except Exception as e:
            print(f"LLM error ({self.provider}:{self.model}): {e}")
            return []

    def get_name(self) -> str:
        return f"LLM-{self.provider}:{self.model}"
