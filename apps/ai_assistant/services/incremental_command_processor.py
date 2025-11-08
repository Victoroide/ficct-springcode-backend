"""Incremental command processor for UML diagram modifications.

Processes natural language commands that MODIFY existing diagrams,
returning DELTA (incremental changes) instead of full diagrams.

Features:
- 90% regex-based pattern matching (fast path)
- 10% AI-powered fallback for complex commands
- English commands only
- Rate limiting per anonymous session
"""

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from .cache_service import CacheService
from .command_patterns import (
    detect_language,
    get_command_patterns,
    normalize_relationship_type,
    normalize_type,
    normalize_visibility,
)
from .openai_service import OpenAIService
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

CACHE_TTL_COMMANDS = 300
RATE_LIMIT_COMMANDS = 100
RATE_LIMIT_WINDOW = 3600


class CommandRequest(BaseModel):
    """Pydantic model for command request validation."""

    command: str = Field(..., min_length=3, max_length=500)
    diagram_id: str = Field(..., min_length=1, max_length=100)
    current_diagram: Dict[str, Any]

    @validator("command")
    def validate_command(cls, v: str) -> str:
        """Validate command is not empty."""
        if not v.strip():
            raise ValueError("Command cannot be empty")
        return v.strip()


class DeltaResponse(BaseModel):
    """Pydantic model for DELTA response."""

    action: str = Field(
        ...,
        pattern=r"^(update_node|add_node|delete_node|update_edge|add_edge|delete_edge)$",
    )
    node_id: Optional[str] = None
    edge_id: Optional[str] = None
    changes: Dict[str, Any]
    description: str


class CommandNotRecognizedError(Exception):
    """Error when command cannot be interpreted."""

    pass


class NodeNotFoundError(Exception):
    """Error when referenced node does not exist."""

    pass


class InvalidOperationError(Exception):
    """Error when operation is not valid."""

    pass


class IncrementalCommandProcessor:
    """Processes incremental commands for UML diagram modifications.

    Features:
    - Regex pattern recognition (90% of cases)
    - AI fallback for complex commands (10%)
    - English commands only
    - Node/edge existence validation
    - 5-minute cache
    - 100 commands/hour rate limiting

    Example:
        >>> processor = IncrementalCommandProcessor()
        >>> delta = processor.process_command(
        ...     "add attribute email (String) to class User",
        ...     "diagram_123",
        ...     {"nodes": [...], "edges": [...]}
        ... )
    """

    def __init__(self):
        """Initialize incremental command processor."""
        logger.info("Incremental Command Processor initialized")

    def process_command(
        self,
        command: str,
        diagram_id: str,
        current_diagram: Dict[str, Any],
        use_cache: bool = True,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process incremental command and return DELTA.

        Args:
            command: Natural language command in English
            diagram_id: Diagram ID
            current_diagram: Current diagram with nodes/edges
            use_cache: Whether to use cache
            session_id: Session ID for rate limiting

        Returns:
            DELTA dictionary with action, changes, description

        Raises:
            CommandNotRecognizedError: If command not recognized
            NodeNotFoundError: If node does not exist
            InvalidOperationError: If operation is invalid
            ValueError: If rate limit exceeded

        Example:
            >>> delta = processor.process_command(
            ...     "add attribute email (String) to class User",
            ...     "diagram_123",
            ...     {"nodes": [...], "edges": [...]}
            ... )
            {
                "action": "update_node",
                "node_id": "node_uuid",
                "changes": {...},
                "description": "Added attribute 'email' (String) to class 'User'"
            }
        """
        request = CommandRequest(
            command=command,
            diagram_id=diagram_id,
            current_diagram=current_diagram,
        )

        diagram_hash = hashlib.md5(
            json.dumps(current_diagram, sort_keys=True).encode()
        ).hexdigest()

        cache_key = {
            "method": "process_incremental_command",
            "command": command.lower(),
            "diagram_hash": diagram_hash,
        }

        if use_cache:
            cached_result = CacheService.get(cache_key)
            if cached_result:
                logger.info("Returning cached command result")
                return cached_result

        if session_id:
            allowed, retry_after = RateLimiter.check_rate_limit(
                session_id,
                "process_command",
                RATE_LIMIT_COMMANDS,
                RATE_LIMIT_WINDOW,
            )
            if not allowed:
                raise ValueError(
                    f"Command rate limit exceeded. Retry after {retry_after}s"
                )

        try:
            delta = self._try_pattern_match(command, current_diagram)

            if delta:
                logger.info("Command matched with regex pattern")
                if use_cache:
                    CacheService.set(cache_key, delta, ttl=CACHE_TTL_COMMANDS)
                return delta

        except (NodeNotFoundError, InvalidOperationError) as e:
            raise

        logger.info("Falling back to AI for complex command")
        delta = self._process_with_ai(command, current_diagram)

        if use_cache:
            CacheService.set(cache_key, delta, ttl=CACHE_TTL_COMMANDS)

        return delta

    def _try_pattern_match(
        self, command: str, diagram: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Try to match command with regex patterns (bilingual).

        Detects language automatically and tries appropriate patterns.

        Args:
            command: Command to process (English or Spanish)
            diagram: Current diagram

        Returns:
            Delta if match found, None otherwise
        """
        language = detect_language(command)
        patterns = get_command_patterns(language)

        logger.debug(f"Detected language: {language}")

        for pattern_name, pattern in patterns.items():
            match = pattern.search(command)
            if match:
                logger.debug(f"Matched pattern: {pattern_name} ({language})")
                return self._handle_pattern_match(pattern_name, match, diagram)

        return None

    def _handle_pattern_match(
        self, pattern_name: str, match, diagram: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle specific pattern match."""
        if "add_attribute" in pattern_name:
            return self._handle_add_attribute(match, diagram)
        elif "remove_attribute" in pattern_name:
            return self._handle_remove_attribute(match, diagram)
        elif "modify_attribute" in pattern_name:
            return self._handle_modify_attribute(match, diagram)
        elif "add_method" in pattern_name:
            return self._handle_add_method(match, diagram)
        elif "remove_method" in pattern_name:
            return self._handle_remove_method(match, diagram)
        elif "add_relationship" in pattern_name:
            return self._handle_add_relationship(match, diagram)
        elif "remove_relationship" in pattern_name:
            return self._handle_remove_relationship(match, diagram)
        elif "rename_class" in pattern_name:
            return self._handle_rename_class(match, diagram)
        elif "change_visibility" in pattern_name:
            return self._handle_change_visibility(match, diagram)

        raise CommandNotRecognizedError(f"Pattern {pattern_name} not handled")

    def _handle_add_attribute(self, match, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """Handle add attribute command."""
        attr_name = match.group(1)
        attr_type = match.group(2)
        class_name = match.group(3)

        node = self._find_node_by_label(class_name, diagram)

        if not node:
            raise NodeNotFoundError(f"Class '{class_name}' not found")

        new_attribute = {
            "id": f"attr-{int(time.time() * 1000)}",
            "name": attr_name,
            "type": normalize_type(attr_type),
            "visibility": "private",
            "isStatic": False,
            "isFinal": False,
        }

        return {
            "action": "update_node",
            "node_id": node["id"],
            "changes": {
                "data.attributes": {"operation": "append", "value": new_attribute}
            },
            "description": f"Added attribute '{attr_name}' ({attr_type}) to class '{class_name}'",
        }

    def _handle_remove_attribute(
        self, match, diagram: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle remove attribute command."""
        attr_name = match.group(1)
        class_name = match.group(2)

        node = self._find_node_by_label(class_name, diagram)

        if not node:
            raise NodeNotFoundError(f"Class '{class_name}' not found")

        return {
            "action": "update_node",
            "node_id": node["id"],
            "changes": {
                "data.attributes": {
                    "operation": "remove",
                    "filter": {"name": attr_name},
                }
            },
            "description": f"Removed attribute '{attr_name}' from class '{class_name}'",
        }

    def _handle_modify_attribute(
        self, match, diagram: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle modify attribute command."""
        old_attr_name = match.group(1)
        class_name = match.group(2)
        new_attr_name = match.group(3)
        new_attr_type = match.group(4)

        node = self._find_node_by_label(class_name, diagram)

        if not node:
            raise NodeNotFoundError(f"Class '{class_name}' not found")

        return {
            "action": "update_node",
            "node_id": node["id"],
            "changes": {
                "data.attributes": {
                    "operation": "update",
                    "filter": {"name": old_attr_name},
                    "value": {
                        "name": new_attr_name,
                        "type": normalize_type(new_attr_type),
                    },
                }
            },
            "description": f"Modified attribute '{old_attr_name}' to '{new_attr_name}' ({new_attr_type}) in class '{class_name}'",
        }

    def _handle_add_method(self, match, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """Handle add method command."""
        method_name = match.group(1)
        params_str = match.group(2)
        return_type = match.group(3)
        class_name = match.group(4)

        node = self._find_node_by_label(class_name, diagram)

        if not node:
            raise NodeNotFoundError(f"Class '{class_name}' not found")

        parameters = self._parse_parameters(params_str)

        new_method = {
            "id": f"method-{int(time.time() * 1000)}",
            "name": method_name,
            "returnType": normalize_type(return_type),
            "visibility": "public",
            "isStatic": False,
            "isAbstract": False,
            "parameters": parameters,
        }

        return {
            "action": "update_node",
            "node_id": node["id"],
            "changes": {"data.methods": {"operation": "append", "value": new_method}},
            "description": f"Added method '{method_name}' returning {return_type} to class '{class_name}'",
        }

    def _handle_remove_method(self, match, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """Handle remove method command."""
        method_name = match.group(1)
        class_name = match.group(2)

        node = self._find_node_by_label(class_name, diagram)

        if not node:
            raise NodeNotFoundError(f"Class '{class_name}' not found")

        return {
            "action": "update_node",
            "node_id": node["id"],
            "changes": {
                "data.methods": {
                    "operation": "remove",
                    "filter": {"name": method_name},
                }
            },
            "description": f"Removed method '{method_name}' from class '{class_name}'",
        }

    def _handle_add_relationship(
        self, match, diagram: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle add relationship command."""
        rel_type_raw = match.group(1)
        source_class = match.group(2)
        target_class = match.group(3)
        multiplicity = match.group(4) if match.lastindex >= 4 else "*"

        source_node = self._find_node_by_label(source_class, diagram)
        target_node = self._find_node_by_label(target_class, diagram)

        if not source_node:
            raise NodeNotFoundError(f"Class '{source_class}' not found")
        if not target_node:
            raise NodeNotFoundError(f"Class '{target_class}' not found")

        rel_type = normalize_relationship_type(rel_type_raw)

        new_edge = {
            "id": f"edge-{int(time.time() * 1000)}",
            "source": source_node["id"],
            "target": target_node["id"],
            "type": "umlRelationship",
            "data": {
                "relationshipType": rel_type,
                "sourceMultiplicity": "1",
                "targetMultiplicity": multiplicity or "*",
                "label": "",
            },
        }

        return {
            "action": "add_edge",
            "edge_id": new_edge["id"],
            "changes": {"edge": {"operation": "create", "value": new_edge}},
            "description": f"Added {rel_type} relationship from '{source_class}' to '{target_class}'",
        }

    def _handle_remove_relationship(
        self, match, diagram: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle remove relationship command."""
        class1 = match.group(1)
        class2 = match.group(2)

        node1 = self._find_node_by_label(class1, diagram)
        node2 = self._find_node_by_label(class2, diagram)

        if not node1:
            raise NodeNotFoundError(f"Class '{class1}' not found")
        if not node2:
            raise NodeNotFoundError(f"Class '{class2}' not found")

        edge = self._find_edge_between_nodes(node1["id"], node2["id"], diagram)

        if not edge:
            raise NodeNotFoundError(
                f"No relationship found between '{class1}' and '{class2}'"
            )

        return {
            "action": "delete_edge",
            "edge_id": edge["id"],
            "changes": {"edge": {"operation": "delete"}},
            "description": f"Removed relationship between '{class1}' and '{class2}'",
        }

    def _handle_rename_class(self, match, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """Handle rename class command."""
        old_name = match.group(1)
        new_name = match.group(2)

        node = self._find_node_by_label(old_name, diagram)

        if not node:
            raise NodeNotFoundError(f"Class '{old_name}' not found")

        return {
            "action": "update_node",
            "node_id": node["id"],
            "changes": {"data.label": {"operation": "replace", "value": new_name}},
            "description": f"Renamed class from '{old_name}' to '{new_name}'",
        }

    def _handle_change_visibility(
        self, match, diagram: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle change visibility command."""
        element_name = match.group(1)
        class_name = match.group(2)
        visibility_raw = match.group(3)

        node = self._find_node_by_label(class_name, diagram)

        if not node:
            raise NodeNotFoundError(f"Class '{class_name}' not found")

        visibility = normalize_visibility(visibility_raw)

        return {
            "action": "update_node",
            "node_id": node["id"],
            "changes": {
                "data.attributes": {
                    "operation": "update",
                    "filter": {"name": element_name},
                    "value": {"visibility": visibility},
                }
            },
            "description": f"Changed visibility of '{element_name}' to {visibility} in class '{class_name}'",
        }

    def _process_with_ai(
        self, command: str, diagram: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process command using AI as fallback.

        Uses existing AzureOpenAIService which handles o-series models automatically.
        """
        nodes = diagram.get("nodes", [])
        class_names = [n.get("data", {}).get("label", "") for n in nodes]

        prompt = f"""Convert this UML modification command to JSON DELTA format.

COMMAND: {command}

AVAILABLE CLASSES: {', '.join(class_names)}
TOTAL NODES: {len(nodes)}

OUTPUT JSON (no markdown, no explanation):
{{
  "action": "update_node" | "add_node" | "delete_node" | "update_edge" | "add_edge" | "delete_edge",
  "node_id": "<uuid if applicable>",
  "edge_id": "<uuid if applicable>",
  "changes": {{
    "path.to.field": {{
      "operation": "append" | "remove" | "replace" | "update",
      "value": <new value>
    }}
  }},
  "description": "Human-readable change description"
}}
"""

        try:
            openai_service = OpenAIService()
            content = openai_service.call_api(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=4096,
                response_format="json",
            )

            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)

            return result

        except Exception as e:
            logger.error(f"AI processing failed: {e}")
            raise CommandNotRecognizedError(f"Could not interpret command: {command}")

    def _find_node_by_label(
        self, label: str, diagram: Dict[str, Any]
    ) -> Optional[Dict]:
        """Find node by class name."""
        nodes = diagram.get("nodes", [])
        for node in nodes:
            node_label = node.get("data", {}).get("label", "")
            if node_label.lower() == label.lower():
                return node
        return None

    def _find_edge_between_nodes(
        self, source_id: str, target_id: str, diagram: Dict[str, Any]
    ) -> Optional[Dict]:
        """Find edge between two nodes (bidirectional)."""
        edges = diagram.get("edges", [])
        for edge in edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            if (source == source_id and target == target_id) or (
                source == target_id and target == source_id
            ):
                return edge
        return None

    def _parse_parameters(self, params_str: str) -> List[Dict[str, str]]:
        """Parse parameter string.

        Args:
            params_str: Parameter string like "name: String, age: int"

        Returns:
            List of parameter dictionaries
        """
        if not params_str.strip():
            return []

        parameters = []
        for param in params_str.split(","):
            param = param.strip()
            if ":" in param:
                parts = param.split(":")
                param_name = parts[0].strip()
                param_type = parts[1].strip()
            else:
                param_name = param
                param_type = "Object"

            parameters.append({"name": param_name, "type": normalize_type(param_type)})

        return parameters
