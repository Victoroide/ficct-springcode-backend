"""
Servicio de caché Redis para AI Assistant.

Proporciona funcionalidad de caché con TTL para reducir costos de API
y mejorar tiempos de respuesta para consultas repetidas.
"""

import hashlib
import json
import logging
from typing import Any, Optional

from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Servicio de gestión de caché Redis con TTL configurable."""

    DEFAULT_TTL = 300  # 5 minutos
    CACHE_PREFIX = "ai_assistant"

    @classmethod
    def _generate_cache_key(cls, key_components: dict) -> str:
        """
        Genera clave de caché única usando hash SHA256.

        Args:
            key_components: Diccionario con componentes de la clave

        Returns:
            Clave de caché única con prefijo

        Example:
            >>> CacheService._generate_cache_key({"query": "test"})
            'ai_assistant:a94a8fe5ccb19ba61c4c0873d391e987982fbbd3'
        """
        key_string = json.dumps(key_components, sort_keys=True)
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()
        return f"{cls.CACHE_PREFIX}:{key_hash}"

    @classmethod
    def get(cls, key_components: dict) -> Optional[Any]:
        """
        Obtiene valor del caché.

        Args:
            key_components: Componentes para generar clave de caché

        Returns:
            Valor cacheado o None si no existe/expiró
        """
        cache_key = cls._generate_cache_key(key_components)
        try:
            value = cache.get(cache_key)
            if value is not None:
                logger.info(f"Cache hit: {cache_key[:50]}...")
            return value
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None

    @classmethod
    def set(
        cls, key_components: dict, value: Any, ttl: int = DEFAULT_TTL
    ) -> bool:
        """
        Guarda valor en caché con TTL.

        Args:
            key_components: Componentes para generar clave de caché
            value: Valor a cachear
            ttl: Time-to-live en segundos (default: 300)

        Returns:
            True si se guardó exitosamente, False en caso contrario
        """
        cache_key = cls._generate_cache_key(key_components)
        try:
            cache.set(cache_key, value, timeout=ttl)
            logger.info(f"Cache set: {cache_key[:50]}... (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    @classmethod
    def delete(cls, key_components: dict) -> bool:
        """
        Elimina valor del caché.

        Args:
            key_components: Componentes para generar clave de caché

        Returns:
            True si se eliminó, False si no existía o hubo error
        """
        cache_key = cls._generate_cache_key(key_components)
        try:
            cache.delete(cache_key)
            logger.info(f"Cache delete: {cache_key[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False

    @classmethod
    def clear_pattern(cls, pattern: str) -> int:
        """
        Elimina todas las claves que coinciden con patrón.

        Args:
            pattern: Patrón de búsqueda (ej: "diagram:*")

        Returns:
            Número de claves eliminadas
        """
        try:
            full_pattern = f"{cls.CACHE_PREFIX}:{pattern}"
            keys = cache.keys(full_pattern)
            if keys:
                cache.delete_many(keys)
                logger.info(f"Cleared {len(keys)} cache keys matching: {pattern}")
                return len(keys)
            return 0
        except Exception as e:
            logger.error(f"Cache clear pattern error: {e}")
            return 0
