"""Ollama local AI client for SQL generation - FREE and no API keys!"""

import httpx
from app.config import get_settings
from app.exceptions import AIAPIError
from app.utils.logger import get_logger

logger = get_logger(__name__)


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
                base_url=self.base_url
            )
        except Exception as e:
            logger.error("ollama_initialization_failed", error=str(e))
            raise AIAPIError(f"Failed to initialize Ollama client: {str(e)}")

    async def generate_content(self, prompt: str) -> str:
        """
        Generate content using Ollama API.

        Args:
            prompt: Input prompt

        Returns:
            str: Generated content

        Raises:
            AIAPIError: If API call fails
        """
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.settings.OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": self.settings.OLLAMA_TEMPERATURE,
                            "stop": ["```"],
                        }
                    }
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
                    response_length=len(content)
                )

                return content

        except httpx.ConnectError:
            logger.error("ollama_connection_failed", error="Cannot connect to Ollama. Is it running?")
            raise AIAPIError(
                "Cannot connect to Ollama. Make sure Ollama is running: 'ollama serve'"
            )
        except httpx.ReadTimeout:
            logger.error("ollama_timeout", timeout=300)
            raise AIAPIError(
                "Ollama took too long to respond (>300s). The model may be overloaded or the prompt too large."
            )
        except Exception as e:
            error_msg = str(e) or type(e).__name__
            logger.error(
                "ollama_content_generation_failed",
                error=error_msg,
                error_type=type(e).__name__,
                prompt=prompt[:200]
            )
            raise AIAPIError(f"Failed to generate content: {error_msg}")


# Global client instance
_ollama_client: OllamaClient = None


def get_ollama_client() -> OllamaClient:
    """Get the global Ollama client instance."""
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client
