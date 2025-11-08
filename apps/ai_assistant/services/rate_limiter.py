"""
Servicio de rate limiting para AI Assistant.

Implementa límites de tasa por IP y sesión para prevenir abuso
y controlar costos de API externa.
"""

import logging
import time
from typing import Optional, Tuple

from django.core.cache import cache

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter basado en Redis con ventanas deslizantes."""

    RATE_LIMIT_PREFIX = "rate_limit"

    @classmethod
    def _get_cache_key(cls, identifier: str, endpoint: str) -> str:
        """
        Genera clave de rate limit.

        Args:
            identifier: Identificador único (IP o session_id)
            endpoint: Nombre del endpoint a limitar

        Returns:
            Clave de cache para rate limiting
        """
        return f"{cls.RATE_LIMIT_PREFIX}:{endpoint}:{identifier}"

    @classmethod
    def check_rate_limit(
        cls, identifier: str, endpoint: str, max_requests: int, window: int
    ) -> Tuple[bool, Optional[int]]:
        """
        Verifica si se excedió el límite de tasa.

        Args:
            identifier: Identificador único (IP o session_id)
            endpoint: Nombre del endpoint
            max_requests: Número máximo de requests permitidos
            window: Ventana de tiempo en segundos

        Returns:
            Tupla (permitido, segundos_hasta_reset)
            - permitido: True si puede proceder, False si excedió límite
            - segundos_hasta_reset: Segundos hasta que se resetee el límite

        Example:
            >>> allowed, retry_after = RateLimiter.check_rate_limit(
            ...     "192.168.1.1", "ask_question", 30, 3600
            ... )
            >>> if not allowed:
            ...     print(f"Rate limit exceeded. Retry after {retry_after}s")
        """
        cache_key = cls._get_cache_key(identifier, endpoint)
        current_time = int(time.time())

        try:
            data = cache.get(cache_key)

            if data is None:
                data = {"requests": [], "window_start": current_time}

            requests = data.get("requests", [])
            window_start = data.get("window_start", current_time)

            cutoff_time = current_time - window
            requests = [req for req in requests if req > cutoff_time]

            if len(requests) >= max_requests:
                oldest_request = min(requests)
                retry_after = window - (current_time - oldest_request)
                logger.warning(
                    f"Rate limit exceeded for {identifier} on {endpoint}. "
                    f"Retry after {retry_after}s"
                )
                return False, max(1, retry_after)

            requests.append(current_time)
            data["requests"] = requests
            data["window_start"] = window_start

            cache.set(cache_key, data, timeout=window)

            remaining = max_requests - len(requests)
            logger.debug(
                f"Rate limit check passed for {identifier}. "
                f"Remaining: {remaining}/{max_requests}"
            )
            return True, None

        except Exception as e:
            logger.error(f"Rate limit check error: {e}. Allowing request.")
            return True, None

    @classmethod
    def reset_limit(cls, identifier: str, endpoint: str) -> bool:
        """
        Resetea el contador de rate limit para un identificador.

        Args:
            identifier: Identificador único (IP o session_id)
            endpoint: Nombre del endpoint

        Returns:
            True si se reseteó exitosamente
        """
        cache_key = cls._get_cache_key(identifier, endpoint)
        try:
            cache.delete(cache_key)
            logger.info(f"Rate limit reset for {identifier} on {endpoint}")
            return True
        except Exception as e:
            logger.error(f"Rate limit reset error: {e}")
            return False

    @classmethod
    def get_remaining_requests(
        cls, identifier: str, endpoint: str, max_requests: int, window: int
    ) -> int:
        """
        Obtiene número de requests restantes en la ventana actual.

        Args:
            identifier: Identificador único (IP o session_id)
            endpoint: Nombre del endpoint
            max_requests: Número máximo de requests permitidos
            window: Ventana de tiempo en segundos

        Returns:
            Número de requests restantes (0 si se excedió el límite)
        """
        cache_key = cls._get_cache_key(identifier, endpoint)
        current_time = int(time.time())

        try:
            data = cache.get(cache_key)
            if data is None:
                return max_requests

            requests = data.get("requests", [])
            cutoff_time = current_time - window
            valid_requests = [req for req in requests if req > cutoff_time]

            return max(0, max_requests - len(valid_requests))

        except Exception as e:
            logger.error(f"Get remaining requests error: {e}")
            return max_requests
