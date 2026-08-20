from typing import Optional
import httpx
from fastapi import HTTPException

try:
    from backend.config.config import OPENAI_API_KEY, OPENAI_API_URL, MODEL
    from backend.utils.timing import set_compose_tokens
except ModuleNotFoundError:
    from config.config import OPENAI_API_KEY, OPENAI_API_URL, MODEL  # type: ignore
    from utils.timing import set_compose_tokens  # type: ignore

class LLMService:
    @staticmethod
    async def get_chat_completion(system_prompt: str, messages: list, timeout: float = 30.0, record_tokens_as: Optional[str] = None, max_tokens: int = 1024) -> str:
        payload_messages = [{"role": "system", "content": system_prompt}] + messages
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    OPENAI_API_URL,
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": MODEL,
                        "messages": payload_messages,
                        "max_tokens": max_tokens,
                        "temperature": 0.65,
                        "stream": False,
                    },
                    timeout=timeout
                )
            
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"OpenAI API error: {resp.text}")
            
            data = resp.json()

            if record_tokens_as == "compose":
                usage = data.get("usage", {})
                p_tok = usage.get("prompt_tokens", -1) if isinstance(usage, dict) else -1
                c_tok = usage.get("completion_tokens", -1) if isinstance(usage, dict) else -1
                set_compose_tokens(p_tok, c_tok)

            return data["choices"][0]["message"]["content"]
            
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Request timed out.")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
