"""Ollama local AI client for SQL generation - FREE and no API keys!"""

import asyncio
import httpx
from app.config import get_settings
from app.exceptions import AIAPIError
from app.utils.logger import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0
RETRY_BACKOFF_FACTOR = 2.0


class OllamaClient:
    """
    Ollama local AI client for SQL generation.

    Advantages:
    - Completely FREE
    - No API keys needed
    - Runs locally
    - Privacy-friendly
    - Works offline
    """

    def __init__(self):
        """Initialize Ollama client."""
        self.settings = get_settings()
        self.base_url = self.settings.OLLAMA_BASE_URL
        self._configure()

    def _configure(self) -> None:
        """Configure Ollama client."""
        try:
            logger.info(
                "ollama_client_initialized",
                model=self.settings.OLLAMA_MODEL,
                base_url=self.base_url,
            )
        except Exception as e:
            logger.error("ollama_initialization_failed", error=str(e))
            raise AIAPIError(f"Failed to initialize Ollama client: {str(e)}")

    async def _retry_with_backoff(self, func, *args, **kwargs):
        """Execute a function with exponential backoff retry logic."""
        last_exception = None
        for attempt in range(MAX_RETRIES):
            try:
                return await func(*args, **kwargs)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.TimeoutException) as e:
                last_exception = e
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY_BASE * (RETRY_BACKOFF_FACTOR**attempt)
                    logger.warning(
                        "ollama_retry_attempt",
                        attempt=attempt + 1,
                        max_retries=MAX_RETRIES,
                        delay_seconds=delay,
                        error=str(e),
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error("ollama_all_retries_failed", error=str(last_exception))
            except Exception:
                raise
        if last_exception:
            raise last_exception

    async def _generate_hf(self, prompt: str) -> str:
        """Generate content via HuggingFace Inference API (OpenAI-compatible endpoint)."""
        if not self.settings.HF_API_TOKEN:
            raise AIAPIError(
                "HF_API_TOKEN is not set. Add it to your environment variables."
            )

        # Strip the trailing ```sql seed — chat completions handles the template
        clean_prompt = prompt.rstrip()
        if clean_prompt.endswith("```sql"):
            clean_prompt = clean_prompt[: -len("```sql")].rstrip()

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api-inference.huggingface.co/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.HF_API_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.HF_MODEL,
                    "messages": [{"role": "user", "content": clean_prompt}],
                    "temperature": 0,
                    "max_tokens": 512,
                    "stream": False,
                },
            )

        if response.status_code == 503:
            raise AIAPIError(
                "HuggingFace model is loading. Wait ~20 seconds and try again."
            )
        if response.status_code == 429:
            raise AIAPIError(
                "HuggingFace rate limit reached. Wait a moment and try again."
            )
        if response.status_code != 200:
            raise AIAPIError(
                f"HuggingFace API returned {response.status_code}: {response.text[:300]}"
            )

        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not content:
            raise AIAPIError("Empty response from HuggingFace API")

        logger.debug(
            "hf_content_generated",
            model=self.settings.HF_MODEL,
            prompt_length=len(clean_prompt),
            response_length=len(content),
        )

        return content

    async def generate_content(self, prompt: str, model_override: str | None = None) -> str:
        """
        Generate content using the configured inference provider.

        Routes to HuggingFace or Ollama based on INFERENCE_PROVIDER setting.
        model_override: if provided, use this model name instead of the server default.
        """
        if self.settings.INFERENCE_PROVIDER == "huggingface":
            try:
                return await self._generate_hf(prompt)
            except AIAPIError:
                raise
            except Exception as e:
                raise AIAPIError(f"HuggingFace generation failed: {str(e)}")

        model_name = model_override or self.settings.OLLAMA_MODEL

        async def _make_request():
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": self.settings.OLLAMA_TEMPERATURE,
                            "stop": ["```"],
                        },
                    },
                )

                if response.status_code != 200:
                    raise AIAPIError(
                        f"Ollama API returned status {response.status_code}: {response.text}"
                    )

                result = response.json()
                content = result.get("response", "")

                if not content:
                    raise AIAPIError("Empty response from Ollama API")

                logger.debug(
                    "ollama_content_generated",
                    prompt_length=len(prompt),
                    response_length=len(content),
                )

                return content

        try:
            result = await self._retry_with_backoff(_make_request)
            if result is None:
                raise AIAPIError("Failed to generate content after retries")
            return result

        except httpx.ConnectError:
            logger.error(
                "ollama_connection_failed",
                error="Cannot connect to Ollama. Is it running?",
            )
            raise AIAPIError(
                "Cannot connect to Ollama. Make sure Ollama is running: 'ollama serve'"
            )
        except httpx.ReadTimeout:
            logger.error("ollama_timeout", timeout=300)
            raise AIAPIError(
                "Ollama took too long to respond (>300s). The model may be overloaded or the prompt too large."
            )
        except AIAPIError:
            raise
        except Exception as e:
            error_msg = str(e) or type(e).__name__
            logger.error(
                "ollama_content_generation_failed",
                error=error_msg,
                error_type=type(e).__name__,
                prompt=prompt[:200],
            )
            raise AIAPIError(f"Failed to generate content: {error_msg}")

    async def check_health(self) -> dict:
        """
        Check if Ollama is accessible and healthy.

        Returns:
            dict: Health status with model availability
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")

                if response.status_code != 200:
                    return {
                        "status": "unhealthy",
                        "error": f"HTTP {response.status_code}",
                        "models": [],
                    }

                data = response.json()
                models = data.get("models", [])
                model_names = [m.get("name", "") for m in models]

                configured_model = self.settings.OLLAMA_MODEL
                is_configured_model_available = any(
                    configured_model in name
                    or configured_model.split(":")[0] in name.split(":")[0]
                    for name in model_names
                )

                return {
                    "status": "healthy"
                    if is_configured_model_available
                    else "degraded",
                    "models": model_names,
                    "configured_model": configured_model,
                    "model_available": is_configured_model_available,
                }

        except httpx.ConnectError:
            return {
                "status": "unhealthy",
                "error": "Cannot connect to Ollama",
                "models": [],
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "models": []}


# Global client instance
_ollama_client: OllamaClient | None = None


def get_ollama_client() -> OllamaClient:
    """Get the global Ollama client instance."""
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client


# ---------------------------------------------------------------------------
# External provider helpers
# ---------------------------------------------------------------------------

def _strip_sql_seed(prompt: str) -> str:
    """Remove trailing ```sql seed that some models don't handle in chat format."""
    clean = prompt.rstrip()
    if clean.endswith("```sql"):
        clean = clean[: -len("```sql")].rstrip()
    return clean


async def _generate_openai(prompt: str, model: str, api_key: str) -> str:
    """Generate SQL via OpenAI chat completions API."""
    if not api_key:
        raise AIAPIError("OpenAI API key is required. Set it in the model selector.")
    clean_prompt = _strip_sql_seed(prompt)
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": clean_prompt}],
                "temperature": 0,
                "max_tokens": 1024,
            },
        )
    if response.status_code == 401:
        raise AIAPIError("Invalid OpenAI API key.")
    if response.status_code == 429:
        raise AIAPIError("OpenAI rate limit reached. Wait a moment and try again.")
    if response.status_code != 200:
        raise AIAPIError(f"OpenAI API returned {response.status_code}: {response.text[:300]}")
    content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        raise AIAPIError("Empty response from OpenAI API")
    logger.debug("openai_content_generated", model=model, response_length=len(content))
    return content


async def _generate_groq(prompt: str, model: str, api_key: str) -> str:
    """Generate SQL via Groq API (OpenAI-compatible endpoint)."""
    if not api_key:
        raise AIAPIError("Groq API key is required. Set it in the model selector.")
    clean_prompt = _strip_sql_seed(prompt)
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": clean_prompt}],
                "temperature": 0,
                "max_tokens": 1024,
            },
        )
    if response.status_code == 401:
        raise AIAPIError("Invalid Groq API key.")
    if response.status_code == 429:
        raise AIAPIError("Groq rate limit reached. Wait a moment and try again.")
    if response.status_code != 200:
        raise AIAPIError(f"Groq API returned {response.status_code}: {response.text[:300]}")
    content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        raise AIAPIError("Empty response from Groq API")
    logger.debug("groq_content_generated", model=model, response_length=len(content))
    return content


async def _generate_google(prompt: str, model: str, api_key: str) -> str:
    """Generate SQL via Google Gemini generateContent API."""
    if not api_key:
        raise AIAPIError("Google API key is required. Set it in the model selector.")
    clean_prompt = _strip_sql_seed(prompt)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": clean_prompt}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 1024},
            },
        )
    if response.status_code == 400:
        raise AIAPIError(f"Google API bad request: {response.text[:300]}")
    if response.status_code == 403:
        raise AIAPIError("Invalid Google API key or API not enabled.")
    if response.status_code == 429:
        raise AIAPIError("Google API rate limit reached. Wait a moment and try again.")
    if response.status_code != 200:
        raise AIAPIError(f"Google API returned {response.status_code}: {response.text[:300]}")
    try:
        content = (
            response.json()
            .get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
    except (KeyError, IndexError):
        content = ""
    if not content:
        raise AIAPIError("Empty response from Google Gemini API")
    logger.debug("google_content_generated", model=model, response_length=len(content))
    return content


async def generate_with_config(
    prompt: str, provider: str, model: str, api_key: str
) -> str:
    """
    Route SQL generation to the correct provider.

    Args:
        prompt: The full prompt to send to the model.
        provider: 'ollama' | 'openai' | 'google'
        model: Model name (empty string = use server/provider default)
        api_key: API key for external providers (ignored for ollama)
    """
    if provider == "openai":
        return await _generate_openai(prompt, model or "gpt-4o-mini", api_key)
    elif provider == "google":
        return await _generate_google(prompt, model or "gemini-1.5-flash", api_key)
    elif provider == "groq":
        return await _generate_groq(prompt, model or "llama-3.3-70b-versatile", api_key)
    else:
        # Ollama (default) — pass model override if provided
        client = get_ollama_client()
        return await client.generate_content(prompt, model_override=model or None)
