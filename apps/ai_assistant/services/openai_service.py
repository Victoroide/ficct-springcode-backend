import logging
import json
import re
from datetime import datetime
from typing import Dict, List
from dotenv import load_dotenv
from base import settings

try:
    import tiktoken
    from openai import AzureOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    # For development without OpenAI dependencies
    OPENAI_AVAILABLE = False
    tiktoken = None
    AzureOpenAI = None


load_dotenv()


def handle_openai_errors(func):
    def wrapper(*args, **kwargs):
        for i in range(3):
            try:
                response = func(*args, **kwargs)
                return response
            except Exception as e:  
                logging.info(f"[OpenAI] Error on request {i+1}: {e}")
                if i < 2:
                    import time
                    time.sleep(1)
                else:
                    raise Exception(f"[OpenAI] Final error after {i} attempts: {e}")
    return wrapper


class OpenAIService():
    def __init__(self):
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI dependencies not available. Install 'openai' and 'tiktoken' packages.")
        
        self.client = AzureOpenAI(
            api_key=settings.OPENAI_AZURE_API_KEY,
            api_version=settings.OPENAI_AZURE_API_VERSION,
            azure_endpoint=settings.OPENAI_AZURE_API_BASE
        )
        self.model = getattr(settings, 'AI_ASSISTANT_DEFAULT_MODEL')
        self.token_limit = 8192
        self.safe_token_limit = 7500
        self.overlap_tokens = 500
        self.encoding = tiktoken.encoding_for_model("gpt-4o")
        self.logger = logging.getLogger(__name__)  

    def chunk_text_by_tokens(self, text, max_tokens=None, overlap_tokens=None):
        max_tokens = max_tokens or self.safe_token_limit
        overlap_tokens = overlap_tokens if overlap_tokens is not None else self.overlap_tokens
        tokens = self.encoding.encode(text)
        chunks = []
        start = 0
        while start < len(tokens):
            end = min(start + max_tokens, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append(chunk_text)
            if end < len(tokens):
                start = end - overlap_tokens
            else:
                start = end
        return chunks

    @handle_openai_errors
    def call_api(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 1000, response_format: str = None) -> str:
        try:
            # Handle special model configurations
            if self.model == "o1-mini":
                for msg in messages:
                    if msg.get("role") == "system":
                        msg["role"] = "user"

            # Prepare completion parameters
            completion_params = {
                'model': self.model,
                'messages': messages,
                'temperature': temperature,
                'max_tokens': max_tokens
            }
            
            # Add response format if specified (for JSON mode)
            if response_format == 'json':
                completion_params['response_format'] = {'type': 'json_object'}
            
            response = self.client.chat.completions.create(**completion_params)
            return response.choices[0].message.content

        except Exception as e:
            self.logger.error(f"OpenAI API call failed: {e}")
            raise
    
    def call_command_processing_api(self, command: str, diagram_context: str = None) -> str:
        """
        Specialized API call for natural language UML command processing.
        
        Args:
            command: Natural language command
            diagram_context: Optional existing diagram context
            
        Returns:
            JSON string with UML elements to be created/modified
        """
        try:
            system_prompt = self._build_command_processing_prompt(diagram_context)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"COMANDO: {command}"}
            ]
            
            # Use JSON mode for structured output
            response = self.call_api(
                messages=messages,
                temperature=0.3,  # Lower temperature for more consistent output
                max_tokens=2000,  # More tokens for complex JSON structures
                response_format='json'
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Command processing API call failed: {e}")
            raise
    
    def _build_command_processing_prompt(self, diagram_context: str = None) -> str:
        """
        Build specialized prompt for natural language UML command processing.
        """
        base_prompt = """
Eres un experto en procesamiento de lenguaje natural para comandos UML en cualquier idioma.

Tu tarea es convertir comandos en lenguaje natural a estructuras JSON compatibles con React Flow para diagramas UML.

COMPORTAMIENTO REQUERIDO:
1. Analiza el comando y extrae entidades UML (clases, atributos, métodos, relaciones)
2. Genera JSON válido con la estructura exacta requerida por React Flow
3. Asigna posiciones inteligentes para nuevos elementos
4. Usa IDs únicos y consistentes
5. Valida tipos de datos y visibilidad

TIPOS DE COMANDOS SOPORTADOS:
- Creación de clases: "Create User class", "Nueva entidad Producto", "Créer classe Utilisateur"
- Definición de atributos: "with attributes name string, age int", "con atributos nombre string, edad int"
- Añadir métodos: "add login method", "añadir método login", "ajouter méthode login"
- Establecer relaciones: "User has many Orders", "Usuario tiene muchos Pedidos"
- Control de visibilidad: "make attribute private", "hacer privado el atributo"
- Herencia: "User inherits from Person", "Usuario hereda de Persona"

FORMATO DE RESPUESTA JSON:
{
  "action": "create_class|add_attribute|add_method|create_relationship|modify_element",
  "elements": [
    {
      "type": "node|edge",
      "data": {
        // React Flow node/edge structure
      }
    }
  ],
  "confidence": 0.95,
  "interpretation": "Descripción de lo que se interpretó"
}

ESTRUCTURA DE NODOS (CLASES):
{
  "id": "class-unique-id",
  "data": {
    "label": "ClassName",
    "attributes": [
      {
        "id": "attr-unique-id",
        "name": "attributeName",
        "type": "String|Integer|Boolean|Date",
        "visibility": "private|public|protected"
      }
    ],
    "methods": [
      {
        "id": "method-unique-id",
        "name": "methodName",
        "returnType": "void|String|Integer",
        "visibility": "private|public|protected",
        "parameters": []
      }
    ],
    "nodeType": "class",
    "isAbstract": false
  },
  "type": "class",
  "position": {"x": 100, "y": 100},
  "style": {"width": 180, "height": "auto"}
}

ESTRUCTURA DE EDGES (RELACIONES):
{
  "id": "edge-unique-id",
  "source": "sourceNodeId",
  "target": "targetNodeId",
  "type": "umlRelationship",
  "data": {
    "relationshipType": "ASSOCIATION|INHERITANCE|COMPOSITION|AGGREGATION",
    "sourceMultiplicity": "1",
    "targetMultiplicity": "1..*",
    "label": ""
  }
}

RECONOCIMIENTO DE ENTIDADES:
- Clases: sustantivos capitalizados (User, Product, Category)
- Atributos: propiedades con tipos (name string, age int, active boolean)
- Métodos: verbos/acciones (login, calculate, get, save)
- Relaciones: "has", "belongs to", "inherits", "extends", "composes"
- Multiplicidad: "one", "many", "several", "0..1", "1..*"

MANEJO DE ERRORES:
- Si el comando es ambiguo, usa valores por defecto razonables
- Si falta información, infiere basándose en el contexto
- Siempre responde con JSON válido
"""
        
        if diagram_context:
            base_prompt += f"\n\nCONTEXTO DEL DIAGRAMA ACTUAL:\n{diagram_context}\n\nConsidera las clases existentes para evitar conflictos y crear relaciones válidas."
        
        return base_prompt
