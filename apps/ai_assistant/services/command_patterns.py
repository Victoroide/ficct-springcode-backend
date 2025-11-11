"""
Command patterns for incremental UML modifications.

Regex patterns for parsing natural language commands in English and Spanish.
Supports bilingual command processing with automatic language detection.
"""

import re
from typing import Dict, Optional, Pattern, Tuple

COMMAND_PATTERNS_EN: Dict[str, Pattern] = {
    "add_attribute": re.compile(
        r"add attribute (\w+)\s*\((\w+)\)\s*to class (\w+)", re.IGNORECASE
    ),
    "remove_attribute": re.compile(
        r"remove attribute (\w+) from class (\w+)", re.IGNORECASE
    ),
    "modify_attribute": re.compile(
        r"change attribute (\w+) in class (\w+) to (\w+)\s*\((\w+)\)", re.IGNORECASE
    ),
    "add_method": re.compile(
        r"add method (\w+)\((.*?)\)\s*returning (\w+) to class (\w+)", re.IGNORECASE
    ),
    "remove_method": re.compile(
        r"remove method (\w+) from class (\w+)", re.IGNORECASE
    ),
    "add_relationship": re.compile(
        r"add (\w+)(?: relationship)? from (\w+) to (\w+)(?: with multiplicity ([\d\.\*]+))?",
        re.IGNORECASE,
    ),
    "remove_relationship": re.compile(
        r"remove relationship between (\w+) and (\w+)", re.IGNORECASE
    ),
    "rename_class": re.compile(r"rename class (\w+) to (\w+)", re.IGNORECASE),
    "change_visibility": re.compile(
        r"change visibility of (\w+) in class (\w+) to (public|private|protected|package)",
        re.IGNORECASE,
    ),
}

COMMAND_PATTERNS_ES: Dict[str, Pattern] = {
    "add_attribute": re.compile(
        r"agregar atributo (\w+)\s*\((\w+)\)\s*a clase (\w+)", re.IGNORECASE
    ),
    "remove_attribute": re.compile(
        r"eliminar atributo (\w+) de clase (\w+)", re.IGNORECASE
    ),
    "modify_attribute": re.compile(
        r"cambiar atributo (\w+) en clase (\w+) a (\w+)\s*\((\w+)\)", re.IGNORECASE
    ),
    "add_method": re.compile(
        r"agregar m[ée]todo (\w+)\((.*?)\)\s*retornando (\w+) a clase (\w+)",
        re.IGNORECASE,
    ),
    "remove_method": re.compile(
        r"eliminar m[ée]todo (\w+) de clase (\w+)", re.IGNORECASE
    ),
    "add_relationship": re.compile(
        r"agregar (\w+)(?: relaci[oó]n)? de (\w+) a (\w+)(?: con multiplicidad ([\d\.\*]+))?",
        re.IGNORECASE,
    ),
    "remove_relationship": re.compile(
        r"eliminar relaci[oó]n entre (\w+) y (\w+)", re.IGNORECASE
    ),
    "rename_class": re.compile(r"renombrar clase (\w+) a (\w+)", re.IGNORECASE),
    "change_visibility": re.compile(
        r"cambiar visibilidad de (\w+) en clase (\w+) a (p[uú]blico|privado|protegido|paquete)",
        re.IGNORECASE,
    ),
}

RELATIONSHIP_TYPES: Dict[str, str] = {
    "association": "ASSOCIATION",
    "aggregation": "AGGREGATION",
    "composition": "COMPOSITION",
    "dependency": "DEPENDENCY",
    "inheritance": "INHERITANCE",
    "realization": "REALIZATION",
    # Spanish
    "asociaci[oó]n": "ASSOCIATION",
    "agregaci[oó]n": "AGGREGATION",
    "composici[oó]n": "COMPOSITION",
    "dependencia": "DEPENDENCY",
    "herencia": "INHERITANCE",
    "realizaci[oó]n": "REALIZATION",
}

VISIBILITY_MAP: Dict[str, str] = {
    "public": "public",
    "private": "private",
    "protected": "protected",
    "package": "package",
    # Spanish
    "público": "public",
    "publico": "public",
    "privado": "private",
    "protegido": "protected",
    "paquete": "package",
}

TYPE_NORMALIZATION: Dict[str, str] = {
    "int": "Integer",
    "integer": "Integer",
    "long": "Long",
    "string": "String",
    "str": "String",
    "double": "Double",
    "float": "Float",
    "bool": "Boolean",
    "boolean": "Boolean",
    "date": "Date",
    "void": "void",
}


def normalize_type(type_str: str) -> str:
    """
    Normalize type string to Java convention.
    """
    normalized = TYPE_NORMALIZATION.get(type_str.lower(), type_str)

    if normalized != "void" and normalized[0].islower():
        normalized = normalized.capitalize()

    return normalized


def normalize_relationship_type(rel_type: str) -> str:
    """
    Normalize relationship type string.
    """
    return RELATIONSHIP_TYPES.get(rel_type.lower(), "ASSOCIATION")


def normalize_visibility(visibility: str) -> str:
    """
    Normalize visibility string (English and Spanish).
    """
    return VISIBILITY_MAP.get(visibility.lower(), "private")


def detect_language(command: str) -> str:
    """
    Detect command language based on Spanish keywords.
    """
    spanish_keywords = [
        "agregar",
        "añadir",
        "eliminar",
        "cambiar",
        "renombrar",
        "método",
        "metodo",
        "atributo",
        "clase",
        "visibilidad",
        "relación",
        "relacion",
        "entre",
        "retornando",
        "multiplicidad",
    ]

    command_lower = command.lower()
    for keyword in spanish_keywords:
        if keyword in command_lower:
            return "es"

    return "en"


def get_command_patterns(language: str) -> Dict[str, Pattern]:
    """
    Get command patterns for specified language.
    """
    if language == "es":
        return COMMAND_PATTERNS_ES
    return COMMAND_PATTERNS_EN
