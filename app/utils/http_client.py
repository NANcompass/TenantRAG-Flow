"""
HTTP Client with retry mechanism and error handling
"""
import httpx
import asyncio
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class HTTPClientError(Exception):
    """Custom exception for HTTP client errors"""

    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[Any] = None):
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(self.message)


class HTTPClient:
    """
    HTTP client with retry mechanism and configurable timeouts
    All configurations loaded from .env
    """

    def __init__(self):
        self.max_retries = settings.MAX_RETRIES
        self.retry_delay = settings.RETRY_DELAY
        self.retry_backoff_factor = settings.RETRY_BACKOFF_FACTOR

    async def post(
        self,
        url: str,
        json_data: Dict[str, Any],
        timeout: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None,
        service_name: str = "Unknown"
    ) -> Dict[str, Any]:
        """
        Async POST request with retry mechanism

        Args:
            url: Target URL
            json_data: JSON payload
            timeout: Request timeout (uses service-specific timeout if not provided)
            headers: Additional headers
            service_name: Service name for logging

        Returns:
            Response JSON data

        Raises:
            HTTPClientError: When request fails after all retries
        """
        default_headers = {"Content-Type": "application/json"}
        if headers:
            default_headers.update(headers)

        current_delay = self.retry_delay
        last_exception = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"[{service_name}] Attempt {attempt}/{self.max_retries}: POST {url}")

                async with httpx.AsyncClient(timeout=timeout or 30) as client:
                    response = await client.post(url, json=json_data, headers=default_headers)

                    if response.status_code >= 200 and response.status_code < 300:
                        logger.info(f"[{service_name}] Request successful on attempt {attempt}")
                        return response.json()

                    # Non-success status code
                    content_type = response.headers.get("content-type", "")
                    error_body = response.json() if "json" in content_type else response.text
                    logger.warning(
                        f"[{service_name}] Request failed with status {response.status_code}: {error_body}"
                    )
                    last_exception = HTTPClientError(
                        f"Request failed with status {response.status_code}",
                        status_code=response.status_code,
                        response_body=error_body
                    )

            except httpx.TimeoutException as e:
                logger.warning(f"[{service_name}] Timeout on attempt {attempt}: {str(e)}")
                last_exception = HTTPClientError(f"Request timeout: {str(e)}")

            except httpx.RequestError as e:
                logger.warning(f"[{service_name}] Connection error on attempt {attempt}: {str(e)}")
                last_exception = HTTPClientError(f"Connection error: {str(e)}")

            except Exception as e:
                logger.warning(f"[{service_name}] Unexpected error on attempt {attempt}: {str(e)}")
                last_exception = HTTPClientError(f"Unexpected error: {str(e)}")

            # Retry delay (not on last attempt)
            if attempt < self.max_retries:
                logger.info(f"[{service_name}] Waiting {current_delay}s before retry...")
                await asyncio.sleep(current_delay)
                current_delay *= self.retry_backoff_factor

        # All retries failed
        logger.error(f"[{service_name}] All {self.max_retries} attempts failed")
        raise last_exception or HTTPClientError("All retry attempts failed")

    def post_sync(
        self,
        url: str,
        json_data: Dict[str, Any],
        timeout: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None,
        service_name: str = "Unknown"
    ) -> Dict[str, Any]:
        """
        Synchronous POST request with retry mechanism

        Args:
            url: Target URL
            json_data: JSON payload
            timeout: Request timeout
            headers: Additional headers
            service_name: Service name for logging

        Returns:
            Response JSON data

        Raises:
            HTTPClientError: When request fails after all retries
        """
        default_headers = {"Content-Type": "application/json"}
        if headers:
            default_headers.update(headers)

        current_delay = self.retry_delay
        last_exception = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"[{service_name}] Attempt {attempt}/{self.max_retries}: POST {url}")

                with httpx.Client(timeout=timeout or 30) as client:
                    response = client.post(url, json=json_data, headers=default_headers)

                    if response.status_code >= 200 and response.status_code < 300:
                        logger.info(f"[{service_name}] Request successful on attempt {attempt}")
                        return response.json()

                    error_body = None
                    try:
                        error_body = response.json()
                    except:
                        error_body = response.text

                    logger.warning(
                        f"[{service_name}] Request failed with status {response.status_code}: {error_body}"
                    )
                    last_exception = HTTPClientError(
                        f"Request failed with status {response.status_code}",
                        status_code=response.status_code,
                        response_body=error_body
                    )

            except httpx.TimeoutException as e:
                logger.warning(f"[{service_name}] Timeout on attempt {attempt}: {str(e)}")
                last_exception = HTTPClientError(f"Request timeout: {str(e)}")

            except httpx.RequestError as e:
                logger.warning(f"[{service_name}] Connection error on attempt {attempt}: {str(e)}")
                last_exception = HTTPClientError(f"Connection error: {str(e)}")

            except Exception as e:
                logger.warning(f"[{service_name}] Unexpected error on attempt {attempt}: {str(e)}")
                last_exception = HTTPClientError(f"Unexpected error: {str(e)}")

            if attempt < self.max_retries:
                logger.info(f"[{service_name}] Waiting {current_delay}s before retry...")
                import time
                time.sleep(current_delay)
                current_delay *= self.retry_backoff_factor

        logger.error(f"[{service_name}] All {self.max_retries} attempts failed")
        raise last_exception or HTTPClientError("All retry attempts failed")


# Global HTTP client instance
http_client = HTTPClient()