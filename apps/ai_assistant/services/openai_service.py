"""
OpenAI Service refactored with complete o1-mini support.

Provides natural language processing functionality with OpenAI models,
optimized for o1-mini (reasoning model) with cache, rate limiting and retry.

CHANGES IN o1-mini vs GPT-4:
- Does NOT support system messages (converted to user messages)
- Does NOT support function calling (use structured outputs with JSON schema)
- Uses reasoning tokens (internal chain of thought)
- Context window: 128K tokens
- Max output: 65K tokens
- Price: $1.1/$4.4 per 1M tokens (vs $30/$60 GPT-4)
- Temperature fixed at 1.0 (not configurable)
"""

import hashlib
import json
import logging
import time
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from pydantic import BaseModel, Field, validator

from .cache_service import CacheService
from .rate_limiter import RateLimiter

try:
    import tiktoken
    from openai import AzureOpenAI
    from openai.types.chat import ChatCompletion

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    tiktoken = None
    AzureOpenAI = None
    ChatCompletion = None

logger = logging.getLogger(__name__)

# Configuration constants
O1_MINI_MODEL = "o1-mini-2024-09-12"
GPT4_MODEL = "gpt-4o"
MAX_COMPLETION_TOKENS_O1 = 65000
MAX_COMPLETION_TOKENS_GPT4 = 4096
REQUEST_TIMEOUT = 60  # seconds
CACHE_TTL = 300  # 5 minutes
RATE_LIMIT_MAX = 30  # requests per hour
RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds


class OpenAIRequest(BaseModel):
    """Pydantic model for OpenAI request validation."""

    prompt: str = Field(..., min_length=1, max_length=10000)
    max_tokens: int = Field(default=4096, ge=1, le=65000)
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    use_cache: bool = Field(default=True)

    @validator("prompt")
    def validate_prompt(cls, v: str) -> str:
        """Validates that prompt is not empty."""
        if not v.strip():
            raise ValueError("Prompt cannot be empty")
        return v


class OpenAIResponse(BaseModel):
    """Pydantic model for structured OpenAI responses."""

    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    sources: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


def retry_with_exponential_backoff(
    max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0
):
    """
    Decorator for retry with exponential backoff.

    Args:
        max_retries: Maximum number of retries
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Configured decorator

    Example:
        >>> @retry_with_exponential_backoff(max_retries=3)
        >>> def api_call():
        ...     return client.chat.completions.create(...)
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded: {e}"
                        )
                        raise

                    delay = min(base_delay * (2**attempt), max_delay)
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} "
                        f"after {delay}s. Error: {e}"
                    )
                    time.sleep(delay)

        return wrapper

    return decorator


class OpenAIService:
    """
    Service for OpenAI API interaction.

    Supports both o1-mini and GPT-4 with the following features:
    - Redis cache with 5 minute TTL
    - Rate limiting of 30 requests/hour per IP
    - Retry with exponential backoff (3 attempts)
    - Timeout of 60 seconds
    - Input validation with Pydantic
    """

    def __init__(self):
        """
        Initializes OpenAI service.

        Raises:
            ImportError: If OpenAI dependencies are not available
            ValueError: If API configuration is invalid
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "OpenAI dependencies not available. "
                "Install 'openai' and 'tiktoken' packages."
            )

        api_key = getattr(settings, "OPENAI_AZURE_API_KEY", "")
        api_base = getattr(settings, "OPENAI_AZURE_API_BASE", "")

        if not api_key or not api_base:
            raise ValueError(
                "OPENAI_AZURE_API_KEY and OPENAI_AZURE_API_BASE "
                "must be configured in settings"
            )

        self.client = AzureOpenAI(
            api_key=api_key,
            api_version=getattr(
                settings, "OPENAI_AZURE_API_VERSION", "2024-02-15-preview"
            ),
            azure_endpoint=api_base,
            timeout=REQUEST_TIMEOUT,
        )

        self.model = getattr(settings, "AI_ASSISTANT_DEFAULT_MODEL", O1_MINI_MODEL)
        self.is_o_series = self._is_o_series_model()
        self.is_o1_mini = self.is_o_series

        if self.is_o_series:
            self.max_tokens = MAX_COMPLETION_TOKENS_O1
        else:
            self.max_tokens = MAX_COMPLETION_TOKENS_GPT4

        try:
            self.encoding = tiktoken.encoding_for_model("gpt-4o")
        except Exception:
            self.encoding = tiktoken.get_encoding("cl100k_base")

        logger.info(
            f"OpenAI Service initialized with model: {self.model} "
            f"(o-series: {self.is_o_series})"
        )

    def _is_o_series_model(self) -> bool:
        """
        Detects if current model is an o-series model.

        o-series models (o1, o1-mini, o4, o4-mini) have different parameter
        requirements than traditional GPT models.

        Returns:
            True if model is o-series, False otherwise

        Examples:
            >>> self.model = "o1-mini"
            >>> self._is_o_series_model()
            True
            >>> self.model = "o4-mini"
            >>> self._is_o_series_model()
            True
            >>> self.model = "gpt-4o"
            >>> self._is_o_series_model()
            False
        """
        model_lower = self.model.lower()
        return (
            model_lower.startswith("o1")
            or model_lower.startswith("o4")
            or model_lower.startswith("o2")
            or model_lower.startswith("o3")
        )

    def _prepare_messages_for_o1(
        self, messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Prepares messages for o1-mini.

        o1-mini does NOT support system messages, so they are converted to user.

        Args:
            messages: List of messages with system/user/assistant roles

        Returns:
            List of messages compatible with o1-mini
        """
        prepared_messages = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                if prepared_messages and prepared_messages[0]["role"] == "user":
                    prepared_messages[0]["content"] = (
                        f"{content}\n\n{prepared_messages[0]['content']}"
                    )
                else:
                    prepared_messages.insert(
                        0, {"role": "user", "content": content}
                    )
            else:
                prepared_messages.append({"role": role, "content": content})

        return prepared_messages

    def _count_tokens(self, text: str) -> int:
        """
        Counts tokens in text.

        Args:
            text: Text to analyze

        Returns:
            Number of tokens
        """
        try:
            return len(self.encoding.encode(text))
        except Exception as e:
            logger.warning(f"Token counting error: {e}")
            return len(text) // 4

    @retry_with_exponential_backoff(max_retries=3, base_delay=1.0, max_delay=60.0)
    def _call_openai_api(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        response_format: Optional[str] = None,
    ) -> ChatCompletion:
        """
        Makes OpenAI API call with retry.

        Args:
            messages: List of conversation messages
            max_tokens: Maximum number of output tokens
            temperature: Temperature for generation (0.0-2.0)
            response_format: Response format ("json" or None)

        Returns:
            OpenAI ChatCompletion object

        Raises:
            Exception: If fails after all retries
        """
        if self.is_o_series:
            messages = self._prepare_messages_for_o1(messages)

        completion_params = {
            "model": self.model,
            "messages": messages,
        }

        if self.is_o_series:
            completion_params["max_completion_tokens"] = max_tokens
        else:
            completion_params["max_tokens"] = max_tokens
            completion_params["temperature"] = temperature

        if response_format == "json" and not self.is_o_series:
            completion_params["response_format"] = {"type": "json_object"}

        logger.info(
            f"Calling OpenAI API: model={self.model}, "
            f"max_tokens={max_tokens}, messages={len(messages)}"
        )

        # Add timeout to prevent indefinite waiting (especially important for o4-mini)
        completion_params["timeout"] = 60.0  # 60 seconds timeout

        response = self.client.chat.completions.create(**completion_params)

        logger.info(
            f"OpenAI API response: usage={response.usage.total_tokens} tokens"
        )

        return response

    def _extract_response_content(self, response) -> str:
        """
        Robustly extract content from OpenAI API response.
        
        o-series models (o1, o1-mini, o4-mini) may have different response structures
        than standard models (gpt-4, gpt-4o). This method tries multiple extraction
        strategies to ensure content is retrieved correctly.
        
        Args:
            response: OpenAI ChatCompletion response object
            
        Returns:
            Extracted content as string
            
        Raises:
            Exception: If content cannot be extracted from any strategy
        """
        logger.info("=" * 80)
        logger.info("RESPONSE EXTRACTION DEBUG")
        logger.info("=" * 80)
        
        # Log response structure for debugging
        logger.info(f"Response type: {type(response)}")
        logger.info(f"Response has choices: {hasattr(response, 'choices')}")
        
        if hasattr(response, 'choices') and len(response.choices) > 0:
            logger.info(f"Choices count: {len(response.choices)}")
            logger.info(f"First choice type: {type(response.choices[0])}")
            logger.info(f"First choice attributes: {dir(response.choices[0])}")
            
            if hasattr(response.choices[0], 'message'):
                logger.info(f"Message attributes: {dir(response.choices[0].message)}")
        
        content = None
        
        try:
            if hasattr(response.choices[0], 'message') and hasattr(response.choices[0].message, 'content'):
                content = response.choices[0].message.content
                if content:
                    logger.info(f"[OK] Strategy 1 SUCCESS: message.content ({len(content)} chars)")
                    return content
                else:
                    logger.warning("[FAIL] Strategy 1: message.content is empty or None")
        except (AttributeError, IndexError) as e:
            logger.warning(f"[FAIL] Strategy 1 failed: {e}")
        
        try:
            if hasattr(response.choices[0], 'text'):
                content = response.choices[0].text
                if content:
                    logger.info(f"[OK] Strategy 2 SUCCESS: choice.text ({len(content)} chars)")
                    return content
                else:
                    logger.warning("[FAIL] Strategy 2: choice.text is empty or None")
        except (AttributeError, IndexError) as e:
            logger.warning(f"[FAIL] Strategy 2 failed: {e}")
        
        try:
            if hasattr(response.choices[0], 'message') and hasattr(response.choices[0].message, 'reasoning_content'):
                reasoning = response.choices[0].message.reasoning_content
                if reasoning:
                    logger.info(f"[OK] Strategy 3 SUCCESS: reasoning_content ({len(reasoning)} chars)")
                    # For o-series, reasoning_content may contain the full response
                    return reasoning
                else:
                    logger.warning("[FAIL] Strategy 3: reasoning_content is empty or None")
        except (AttributeError, IndexError) as e:
            logger.warning(f"[FAIL] Strategy 3 failed: {e}")
        
        try:
            response_dict = response.model_dump()
            logger.info(f"Response dict keys: {response_dict.keys()}")
            
            if 'choices' in response_dict and len(response_dict['choices']) > 0:
                choice_dict = response_dict['choices'][0]
                logger.info(f"Choice dict keys: {choice_dict.keys()}")
                
                if 'message' in choice_dict and 'content' in choice_dict['message']:
                    content = choice_dict['message']['content']
                    if content:
                        logger.info(f"[OK] Strategy 4 SUCCESS: dict access ({len(content)} chars)")
                        return content
                    else:
                        logger.warning("[FAIL] Strategy 4: dict content is empty or None")
        except Exception as e:
            logger.warning(f"[FAIL] Strategy 4 failed: {e}")
        
        try:
            import json
            response_json = response.model_dump_json()
            response_dict = json.loads(response_json)
            
            content = response_dict.get('choices', [{}])[0].get('message', {}).get('content')
            if content:
                logger.info(f"[OK] Strategy 5 SUCCESS: JSON parse ({len(content)} chars)")
                return content
            else:
                logger.warning("[FAIL] Strategy 5: JSON content is empty or None")
        except Exception as e:
            logger.warning(f"[FAIL] Strategy 5 failed: {e}")
        
        logger.error("=" * 80)
        logger.error("CRITICAL: ALL EXTRACTION STRATEGIES FAILED")
        logger.error("=" * 80)
        logger.error(f"Full response object: {response}")
        
        try:
            logger.error(f"Response dict: {response.model_dump()}")
        except:
            logger.error("Could not dump response to dict")
        
        raise Exception(
            f"Failed to extract content from OpenAI response after trying all strategies. "
            f"Response type: {type(response)}, "
            f"Model: {self.model}, "
            f"Is o-series: {self.is_o_series}"
        )

    def call_api(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> str:
        """
        Generic API call method for AI Assistant service.

        Args:
            messages: List of conversation messages with role and content
            max_tokens: Maximum tokens for response
            temperature: Temperature for generation

        Returns:
            Response content as string

        Raises:
            Exception: If API call fails
        """
        try:
            logger.info(f"Generic API call with {len(messages)} messages")
            
            response = self._call_openai_api(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format=None
            )
            
            # Use robust extraction for o-series compatibility
            content = self._extract_response_content(response)
            logger.info(f"Generic API call successful: {len(content)} chars")
            
            return content
            
        except Exception as e:
            logger.error(f"Generic API call failed: {e}", exc_info=True)
            raise

    def ask_question(
        self,
        question: str,
        context: Optional[str] = None,
        use_cache: bool = True,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Asks general question about UML/Spring Boot.

        Args:
            question: User question
            context: Optional additional context
            use_cache: Whether to use cache (default: True)
            session_id: Session ID for rate limiting

        Returns:
            Dictionary with answer, confidence, sources

        Raises:
            ValueError: If question is empty or rate limit exceeded
        """
        request = OpenAIRequest(
            prompt=question, use_cache=use_cache, max_tokens=4096, temperature=0.7
        )

        cache_key = {"method": "ask_question", "question": question, "context": context}

        if use_cache:
            cached_response = CacheService.get(cache_key)
            if cached_response:
                logger.info("Returning cached response for ask_question")
                return cached_response

        if session_id:
            allowed, retry_after = RateLimiter.check_rate_limit(
                session_id, "ask_question", RATE_LIMIT_MAX, RATE_LIMIT_WINDOW
            )
            if not allowed:
                raise ValueError(
                    f"Rate limit exceeded. Retry after {retry_after} seconds"
                )

        prompt = self._build_question_prompt(question, context)

        messages = [{"role": "user", "content": prompt}]

        try:
            response = self._call_openai_api(
                messages=messages,
                max_tokens=4096,
                temperature=0.7,
                response_format="json" if not self.is_o_series else None,
            )

            # Use robust extraction for o-series compatibility
            content = self._extract_response_content(response)

            if self.is_o_series:
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError:
                    parsed = {
                        "answer": content,
                        "confidence": 0.8,
                        "sources": ["o1-mini reasoning"],
                    }
            else:
                parsed = json.loads(content)

            result = {
                "answer": parsed.get("answer", content),
                "confidence": parsed.get("confidence", 0.85),
                "sources": parsed.get("sources", []),
                "metadata": {
                    "model": self.model,
                    "tokens_used": response.usage.total_tokens,
                    "timestamp": time.time(),
                },
            }

            if use_cache:
                CacheService.set(cache_key, result, ttl=CACHE_TTL)

            return result

        except Exception as e:
            logger.error(f"Error in ask_question: {e}")
            raise

    def _build_question_prompt(
        self, question: str, context: Optional[str] = None
    ) -> str:
        """
        Construye prompt para preguntas generales.

        Args:
            question: User question
            context: Optional additional context

        Returns:
            Prompt completo formateado
        """
        base_prompt = f"""You are an expert in UML and Spring Boot.

QUESTION: {question}"""

        if context:
            base_prompt += f"\n\nCONTEXT: {context}"

        base_prompt += """

RESPOND IN JSON FORMAT:
{
  "answer": "detailed answer in natural language",
  "confidence": 0.95,
  "sources": ["UML 2.5 spec", "Spring Boot docs"]
}

RULES:
- Precise and technical answers
- Include examples when useful
- Cite reliable sources
- Confidence between 0.0 and 1.0
"""

        return base_prompt

    def ask_about_diagram(
        self,
        question: str,
        diagram_data: Dict[str, Any],
        use_cache: bool = True,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Asks contextual question about specific diagram.

        Args:
            question: User question
            diagram_data: Diagram data (nodes, edges)
            use_cache: Whether to use cache
            session_id: Session ID for rate limiting

        Returns:
            Dictionary with answer, confidence, suggestions
        """
        diagram_hash = hashlib.md5(
            json.dumps(diagram_data, sort_keys=True).encode()
        ).hexdigest()

        cache_key = {
            "method": "ask_about_diagram",
            "question": question,
            "diagram_hash": diagram_hash,
        }

        if use_cache:
            cached_response = CacheService.get(cache_key)
            if cached_response:
                return cached_response

        if session_id:
            allowed, retry_after = RateLimiter.check_rate_limit(
                session_id, "ask_about_diagram", RATE_LIMIT_MAX, RATE_LIMIT_WINDOW
            )
            if not allowed:
                raise ValueError(
                    f"Rate limit exceeded. Retry after {retry_after}s"
                )

        context = self._build_diagram_context(diagram_data)
        prompt = self._build_diagram_question_prompt(question, context)

        messages = [{"role": "user", "content": prompt}]

        try:
            response = self._call_openai_api(
                messages=messages,
                max_tokens=4096,
                temperature=0.7,
                response_format="json" if not self.is_o_series else None,
            )

            # Use robust extraction for o-series compatibility
            content = self._extract_response_content(response)

            if self.is_o_series:
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError:
                    parsed = {"answer": content, "confidence": 0.8, "suggestions": []}
            else:
                parsed = json.loads(content)

            result = {
                "answer": parsed.get("answer", content),
                "confidence": parsed.get("confidence", 0.85),
                "suggestions": parsed.get("suggestions", []),
                "metadata": {
                    "model": self.model,
                    "tokens_used": response.usage.total_tokens,
                },
            }

            if use_cache:
                CacheService.set(cache_key, result, ttl=CACHE_TTL)

            return result

        except Exception as e:
            logger.error(f"Error in ask_about_diagram: {e}")
            raise

    def _build_diagram_context(self, diagram_data: Dict[str, Any]) -> str:
        """
        Builds diagram context for prompt.

        Args:
            diagram_data: Diagram data with nodes and edges

        Returns:
            String with formatted context
        """
        nodes = diagram_data.get("nodes", [])
        edges = diagram_data.get("edges", [])

        context_parts = [f"The diagram has {len(nodes)} classes and {len(edges)} relationships."]

        if nodes:
            context_parts.append("\nCLASSES:")
            for node in nodes[:10]:
                node_data = node.get("data", {})
                label = node_data.get("label", "Unknown")
                attrs = node_data.get("attributes", [])
                methods = node_data.get("methods", [])
                context_parts.append(
                    f"- {label}: {len(attrs)} attributes, {len(methods)} methods"
                )

        if edges:
            context_parts.append("\nRELATIONSHIPS:")
            for edge in edges[:10]:
                edge_data = edge.get("data", {})
                rel_type = edge_data.get("relationshipType", "UNKNOWN")
                context_parts.append(f"- {rel_type}")

        return "\n".join(context_parts)

    def _build_diagram_question_prompt(self, question: str, context: str) -> str:
        """Builds prompt for diagram questions."""
        return f"""You are an expert in UML diagram analysis.

DIAGRAM CONTEXT:
{context}

QUESTION: {question}

RESPOND IN JSON FORMAT:
{{
  "answer": "detailed answer analyzing the diagram",
  "confidence": 0.95,
  "suggestions": ["suggestion 1", "suggestion 2"]
}}
"""

    def process_command(
        self,
        command: str,
        current_diagram: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Processes NLP command to generate UML elements.

        Args:
            command: Natural language command
            current_diagram: Optional current diagram
            use_cache: Whether to use cache
            session_id: Session ID for rate limiting

        Returns:
            Dictionary with action, elements, confidence
        """
        cache_key = {
            "method": "process_command",
            "command": command,
        }

        if use_cache:
            cached_response = CacheService.get(cache_key)
            if cached_response:
                return cached_response

        if session_id:
            allowed, retry_after = RateLimiter.check_rate_limit(
                session_id, "process_command", RATE_LIMIT_MAX, RATE_LIMIT_WINDOW
            )
            if not allowed:
                raise ValueError(f"Rate limit exceeded. Retry after {retry_after}s")

        prompt = self._build_command_prompt(command, current_diagram)
        messages = [{"role": "user", "content": prompt}]

        try:
            response = self._call_openai_api(
                messages=messages,
                max_tokens=4096,
                temperature=0.2,
                response_format="json" if not self.is_o_series else None,
            )

            # Use robust extraction for o-series compatibility
            content = self._extract_response_content(response)

            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                result = {
                    "action": "unknown",
                    "elements": [],
                    "confidence": 0.5,
                    "interpretation": content,
                }

            if use_cache:
                CacheService.set(cache_key, result, ttl=CACHE_TTL)

            return result

        except Exception as e:
            logger.error(f"Error in process_command: {e}")
            raise

    def call_command_processing_api(self, command: str, current_diagram_data: dict = None) -> str:
        """Direct natural language to React Flow JSON conversion.
        
        Args:
            command: Natural language command
            current_diagram_data: Current diagram state with nodes and edges
            
        Returns:
            JSON string with exact React Flow node/edge structures
        """
        import time
        start_time = time.time()
        
        try:
            logger.info(f"Starting command processing API call for: {command[:100]}")
            
            system_prompt = self._build_direct_json_prompt(current_diagram_data)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": command}
            ]

            logger.info("Calling OpenAI API for command processing...")
            
            response = self._call_openai_api(
                messages=messages,
                max_tokens=5000,  # Increased for o4-mini: needs tokens for reasoning (2000+) + output (2000+)
                temperature=0.7,
                response_format=None,
            )
            
            elapsed_time = time.time() - start_time
            logger.info(f"OpenAI API call completed in {elapsed_time:.2f} seconds")
            
            # Extract content using robust method for o-series compatibility
            content = self._extract_response_content(response)
            logger.info(f"Successfully extracted content: {len(content)} chars")
            
            return content
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Command processing API call failed after {elapsed_time:.2f} seconds: {e}")
            raise

    def _build_direct_json_prompt(self, current_diagram_data: dict = None) -> str:
        """Build comprehensive prompt for direct React Flow JSON generation."""
        import time
        timestamp_ms = int(time.time() * 1000)
        
        base_prompt = f"""
⚠️ CRITICAL OUTPUT FORMAT REQUIREMENT ⚠️

YOU MUST RETURN ONLY PURE JSON. NO EXPLANATORY TEXT. NO MARKDOWN.

INCORRECT RESPONSE EXAMPLES:
❌ "Here's the diagram: ``````"
❌ "I'll create a User class: {{...}}"
❌ "```json\n{{...}}\n```"

CORRECT RESPONSE FORMAT:
✅ Your response must START with {{ and END with }}
✅ First character: {{
✅ Last character: }}
✅ Nothing before or after the JSON object
✅ Response must be parseable by json.loads() in Python

You are a UML diagram generator that converts natural language to EXACT React Flow JSON.

Your ONLY task is to generate VALID React Flow node/edge JSON structures. NEVER return empty elements arrays.

CRITICAL RULES:
1. ALWAYS generate REAL elements - NEVER return empty arrays
2. Use unique IDs with timestamp: class-{timestamp_ms}, attr-{timestamp_ms}
3. Position new elements intelligently to avoid overlaps
4. For "Crea clase User con id, nombre, apellido, sexo" create actual User class with those 4 attributes
5. Support Spanish, English, French: id=int/Long, nombre/name=String, apellido/lastname=String, sexo/gender=String
6. ALWAYS populate elements array when command is clear

EXACT JSON STRUCTURE:
{{
  "action": "create_class",
  "elements": [
    {{
      "type": "node",
      "data": {{
        "id": "class-{timestamp_ms}",
        "data": {{
          "label": "ClassName",
          "attributes": [
            {{"id": "attr-{timestamp_ms}-1", "name": "attributeName", "type": "String", "visibility": "private", "isStatic": false, "isFinal": false}}
          ],
          "methods": [],
          "nodeType": "class",
          "isAbstract": false
        }},
        "type": "class",
        "position": {{"x": 400, "y": 200}},
        "width": 180,
        "height": 140
      }}
    }}
  ],
  "confidence": 0.95,
  "interpretation": "Created User class with specified attributes"
}}

EXAMPLE COMMANDS AND RESPONSES:

1. "Crea una clase User que tenga id, nombre, apellido y sexo"
Response:
{{
  "action": "create_class",
  "elements": [
    {{
      "type": "node",
      "data": {{
        "id": "class-{timestamp_ms}",
        "data": {{
          "label": "User",
          "attributes": [
            {{"id": "attr-{timestamp_ms}-1", "name": "id", "type": "Long", "visibility": "private", "isStatic": false, "isFinal": false}},
            {{"id": "attr-{timestamp_ms}-2", "name": "nombre", "type": "String", "visibility": "private", "isStatic": false, "isFinal": false}},
            {{"id": "attr-{timestamp_ms}-3", "name": "apellido", "type": "String", "visibility": "private", "isStatic": false, "isFinal": false}},
            {{"id": "attr-{timestamp_ms}-4", "name": "sexo", "type": "String", "visibility": "private", "isStatic": false, "isFinal": false}}
          ],
          "methods": [],
          "nodeType": "class",
          "isAbstract": false
        }},
        "type": "class",
        "position": {{"x": 400, "y": 200}},
        "width": 180,
        "height": 200
      }}
    }}
  ],
  "confidence": 0.95,
  "interpretation": "Se creó la clase User con los atributos: id (Long), nombre (String), apellido (String), sexo (String)"
}}

2. "Create Product class with name, price, and stock"
Response:
{{
  "action": "create_class",
  "elements": [
    {{
      "type": "node",
      "data": {{
        "id": "class-{timestamp_ms}",
        "data": {{
          "label": "Product",
          "attributes": [
            {{"id": "attr-{timestamp_ms}-1", "name": "name", "type": "String", "visibility": "private", "isStatic": false, "isFinal": false}},
            {{"id": "attr-{timestamp_ms}-2", "name": "price", "type": "Double", "visibility": "private", "isStatic": false, "isFinal": false}},
            {{"id": "attr-{timestamp_ms}-3", "name": "stock", "type": "Integer", "visibility": "private", "isStatic": false, "isFinal": false}}
          ],
          "methods": [],
          "nodeType": "class",
          "isAbstract": false
        }},
        "type": "class",
        "position": {{"x": 500, "y": 300}},
        "width": 180,
        "height": 180
      }}
    }}
  ],
  "confidence": 0.95,
  "interpretation": "Created Product class with name (String), price (Double), and stock (Integer) attributes"
}}

TYPE MAPPINGS:
- id, código, code → Long
- nombre, name, apellido, lastname → String  
- edad, age → Integer
- precio, price, costo, cost → Double
- activo, active, enabled → Boolean
- fecha, date, createdAt → Date
- descripción, description, texto, text → String
- cantidad, quantity, stock → Integer
- email, correo → String
- teléfono, phone → String
- dirección, address → String
- sexo, gender → String

POSITIONING STRATEGY:
- First class: {{"x": 400, "y": 200}}
- Second class: {{"x": 700, "y": 200}}
- Third class: {{"x": 400, "y": 450}}
- Fourth class: {{"x": 700, "y": 450}}
- Avoid overlaps with existing nodes

RELATIONSHIP STRUCTURE:
{{
  "type": "edge",
  "data": {{
    "id": "edge-{timestamp_ms}",
    "source": "class-source-id",
    "target": "class-target-id",
    "type": "umlRelationship",
    "data": {{
      "relationshipType": "ASSOCIATION",
      "sourceMultiplicity": "1",
      "targetMultiplicity": "*",
      "label": ""
    }}
  }}
}}

CRITICAL: Generate timestamp-based unique IDs, create REAL attributes for all mentioned fields, and ALWAYS return populated elements arrays.
"""
        
        if current_diagram_data:
            nodes = current_diagram_data.get('nodes', [])
            edges = current_diagram_data.get('edges', [])
            
            if nodes:
                node_info = []
                for node in nodes[:5]:  # Limit to avoid token overflow
                    node_data = node.get('data', {})
                    label = node_data.get('label', 'Unknown')
                    node_id = node.get('id', '')
                    node_info.append(f"- {label} (ID: {node_id})")
                
                context = f"\n\nEXISTING DIAGRAM CONTEXT:\nClasses: {', '.join([n.get('data', {}).get('label', '') for n in nodes])}\n" + "\n".join(node_info)
                context += f"\n\nPosition new classes to avoid these existing positions. Use x > 100 and y > 100."
                base_prompt += context
        
        return base_prompt

    def analyze_diagram(
        self,
        diagram_data: Dict[str, Any],
        use_cache: bool = True,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyzes complete diagram with AI.

        Args:
            diagram_data: Complete diagram data
            use_cache: Whether to use cache
            session_id: Session ID for rate limiting

        Returns:
            Dictionary with analysis, patterns, SOLID violations
        """
        diagram_hash = hashlib.md5(
            json.dumps(diagram_data, sort_keys=True).encode()
        ).hexdigest()

        cache_key = {"method": "analyze_diagram", "diagram_hash": diagram_hash}

        if use_cache:
            cached_response = CacheService.get(cache_key)
            if cached_response:
                return cached_response

        if session_id:
            allowed, retry_after = RateLimiter.check_rate_limit(
                session_id, "analyze_diagram", RATE_LIMIT_MAX, RATE_LIMIT_WINDOW
            )
            if not allowed:
                raise ValueError(f"Rate limit exceeded. Retry after {retry_after}s")

        context = self._build_diagram_context(diagram_data)
        prompt = self._build_analysis_prompt(context)

        messages = [{"role": "user", "content": prompt}]

        try:
            response = self._call_openai_api(
                messages=messages,
                max_tokens=4096,
                temperature=0.7,
                response_format="json" if not self.is_o_series else None,
            )

            # Use robust extraction for o-series compatibility
            content = self._extract_response_content(response)

            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                result = {"analysis": content, "patterns": [], "solid_violations": []}

            if use_cache:
                CacheService.set(cache_key, result, ttl=CACHE_TTL)

            return result

        except Exception as e:
            logger.error(f"Error in analyze_diagram: {e}")
            raise

    def _build_analysis_prompt(self, context: str) -> str:
        """Builds prompt for diagram analysis."""
        return f"""Analyze this UML diagram in depth.

{context}

RESPOND IN JSON FORMAT:
{{
  "analysis": "general diagram analysis",
  "patterns": ["detected pattern 1", "pattern 2"],
  "solid_violations": ["SRP violation", "OCP violation"],
  "recommendations": ["recommendation 1", "recommendation 2"],
  "complexity_score": 7.5,
  "quality_score": 8.0
}}

Evaluate:
- Complexity (1-10)
- Quality (1-10)
- Design patterns
- SOLID violations
- Improvement recommendations
"""
