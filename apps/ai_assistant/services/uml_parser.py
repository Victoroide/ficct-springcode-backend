"""UML element parser from OCR text.

Parses extracted text to identify UML classes, attributes, methods, and relationships.
"""

import logging
import re
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

VISIBILITY_PATTERNS = {
    "+": "public",
    "-": "private",
    "#": "protected",
    "~": "package",
}

TYPE_MAPPING = {
    "int": "Integer",
    "integer": "Integer",
    "long": "Long",
    "string": "String",
    "str": "String",
    "double": "Double",
    "float": "Float",
    "bool": "Boolean",
    "boolean": "Boolean",
    "void": "void",
    "date": "Date",
}


class NoUMLDetectedError(Exception):
    """Error when no UML elements detected in text."""

    pass


class UMLParser:
    """
    Parser for UML elements from OCR text.

    Features:
    - Class name extraction
    - Attribute parsing (name, type, visibility)
    - Method parsing (name, parameters, return type)
    - Stereotype detection (<<abstract>>, <<interface>>)
    - Relationship inference

    Example:
        >>> parser = UMLParser()
        >>> elements = parser.parse_text_to_elements(ocr_text, boxes)
    """

    def __init__(self):
        """Initialize UML parser."""
        self.class_pattern = re.compile(
            r"^([A-Z][a-zA-Z0-9_]*)\s*$", re.MULTILINE
        )

        self.attribute_pattern = re.compile(
            r"^([\+\-\#\~])?\s*([a-z][a-zA-Z0-9_]*)\s*:\s*([A-Za-z][A-Za-z0-9_<>\[\]]*)",
            re.MULTILINE,
        )

        self.method_pattern = re.compile(
            r"^([\+\-\#\~])?\s*([a-z][a-zA-Z0-9_]*)\s*\((.*?)\)\s*:\s*([A-Za-z][A-Za-z0-9_<>\[\]]*)",
            re.MULTILINE,
        )

        self.stereotype_pattern = re.compile(r"<<(\w+)>>")

    def parse_text_to_elements(
        self, text: str, boxes: List[Dict[str, any]]
    ) -> Dict[str, any]:
        """
        Parse OCR text and boxes to UML elements.

        Args:
            text: Full OCR extracted text
            boxes: List of text boxes with bbox and text

        Returns:
            Dictionary with nodes and edges

        Raises:
            NoUMLDetectedError: If no classes found
        """
        classes = self._extract_classes(text, boxes)

        if not classes:
            raise NoUMLDetectedError("No UML classes detected in image")

        nodes = []
        for class_data in classes:
            node = self._create_node_from_class(class_data)
            nodes.append(node)

        edges = self._infer_relationships(classes)

        logger.info(
            f"Parsed {len(nodes)} classes, {len(edges)} relationships"
        )

        return {"nodes": nodes, "edges": edges}

    def _extract_classes(
        self, text: str, boxes: List[Dict[str, any]]
    ) -> List[Dict[str, any]]:
        """
        Extract class information from text and boxes.

        Args:
            text: Full text
            boxes: Bounding boxes with text

        Returns:
            List of class data dictionaries
        """
        classes = []

        lines = text.split("\n")
        current_class = None
        current_section = None

        for line in lines:
            line = line.strip()

            if not line:
                continue

            if self._is_class_name(line):
                if current_class:
                    classes.append(current_class)

                current_class = {
                    "name": line,
                    "attributes": [],
                    "methods": [],
                    "stereotypes": [],
                    "is_abstract": False,
                    "is_interface": False,
                }
                current_section = None

            elif current_class:
                stereotype_match = self.stereotype_pattern.search(line)
                if stereotype_match:
                    stereotype = stereotype_match.group(1)
                    current_class["stereotypes"].append(stereotype)

                    if stereotype.lower() in ["abstract", "abstracta"]:
                        current_class["is_abstract"] = True
                    elif stereotype.lower() in [
                        "interface",
                        "interfaz",
                    ]:
                        current_class["is_interface"] = True

                elif self._is_separator(line):
                    current_section = (
                        "methods"
                        if current_section == "attributes"
                        else "attributes"
                    )

                elif self._is_attribute(line):
                    attr = self._parse_attribute(line)
                    if attr:
                        current_class["attributes"].append(attr)
                    current_section = "attributes"

                elif self._is_method(line):
                    method = self._parse_method(line)
                    if method:
                        current_class["methods"].append(method)
                    current_section = "methods"

        if current_class:
            classes.append(current_class)

        return classes

    def _is_class_name(self, line: str) -> bool:
        """Check if line is a class name."""
        if not line:
            return False

        if len(line) > 50:
            return False

        if line[0].isupper() and line.replace("_", "").isalnum():
            return True

        return False

    def _is_separator(self, line: str) -> bool:
        """Check if line is a section separator."""
        return all(c in "-=_" for c in line) and len(line) > 2

    def _is_attribute(self, line: str) -> bool:
        """Check if line is an attribute."""
        return bool(self.attribute_pattern.match(line))

    def _is_method(self, line: str) -> bool:
        """Check if line is a method."""
        return bool(self.method_pattern.match(line))

    def _parse_attribute(self, line: str) -> Optional[Dict[str, any]]:
        """Parse attribute line."""
        match = self.attribute_pattern.match(line)
        if not match:
            return None

        visibility_symbol = match.group(1) or "-"
        name = match.group(2)
        type_str = match.group(3)

        return {
            "id": f"attr-{int(time.time() * 1000)}-{hash(name) % 10000}",
            "name": name,
            "type": self._normalize_type(type_str),
            "visibility": VISIBILITY_PATTERNS.get(
                visibility_symbol, "private"
            ),
            "isStatic": False,
            "isFinal": False,
        }

    def _parse_method(self, line: str) -> Optional[Dict[str, any]]:
        """Parse method line."""
        match = self.method_pattern.match(line)
        if not match:
            return None

        visibility_symbol = match.group(1) or "+"
        name = match.group(2)
        params_str = match.group(3)
        return_type = match.group(4)

        parameters = self._parse_parameters(params_str)

        return {
            "id": f"method-{int(time.time() * 1000)}-{hash(name) % 10000}",
            "name": name,
            "returnType": self._normalize_type(return_type),
            "visibility": VISIBILITY_PATTERNS.get(
                visibility_symbol, "public"
            ),
            "isStatic": False,
            "isAbstract": False,
            "parameters": parameters,
        }

    def _parse_parameters(self, params_str: str) -> List[Dict[str, str]]:
        """Parse method parameters."""
        if not params_str.strip():
            return []

        parameters = []
        for param in params_str.split(","):
            param = param.strip()

            if ":" in param:
                parts = param.split(":")
                param_name = parts[0].strip()
                param_type = parts[1].strip() if len(parts) > 1 else "Object"
            else:
                param_name = param
                param_type = "Object"

            parameters.append(
                {
                    "name": param_name,
                    "type": self._normalize_type(param_type),
                }
            )

        return parameters

    def _normalize_type(self, type_str: str) -> str:
        """Normalize type string to Java convention."""
        normalized = TYPE_MAPPING.get(type_str.lower(), type_str)

        if normalized != "void" and normalized[0].islower():
            normalized = normalized.capitalize()

        return normalized

    def _create_node_from_class(
        self, class_data: Dict[str, any]
    ) -> Dict[str, any]:
        """Create React Flow node from class data."""
        node_id = f"class-{int(time.time() * 1000)}-{hash(class_data['name']) % 10000}"

        return {
            "id": node_id,
            "type": "classNode",
            "data": {
                "label": class_data["name"],
                "attributes": class_data["attributes"],
                "methods": class_data["methods"],
                "nodeType": (
                    "interface"
                    if class_data["is_interface"]
                    else "class"
                ),
                "isAbstract": class_data["is_abstract"],
            },
        }

    def _infer_relationships(
        self, classes: List[Dict[str, any]]
    ) -> List[Dict[str, any]]:
        """
        Infer relationships between classes based on attributes.

        Args:
            classes: List of class data

        Returns:
            List of edge dictionaries
        """
        edges = []
        class_names = {c["name"] for c in classes}

        for i, source_class in enumerate(classes):
            for attr in source_class["attributes"]:
                attr_type = attr["type"]

                if attr_type in class_names:
                    edge_id = f"edge-{int(time.time() * 1000)}-{i}"

                    target_class = next(
                        c for c in classes if c["name"] == attr_type
                    )

                    edges.append(
                        {
                            "id": edge_id,
                            "source": f"class-{hash(source_class['name']) % 10000}",
                            "target": f"class-{hash(target_class['name']) % 10000}",
                            "type": "umlRelationship",
                            "data": {
                                "relationshipType": "ASSOCIATION",
                                "sourceMultiplicity": "1",
                                "targetMultiplicity": "*",
                                "label": attr["name"],
                            },
                        }
                    )

        return edges
