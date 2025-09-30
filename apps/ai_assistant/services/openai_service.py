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

            if self.model == "o1-mini":
                for msg in messages:
                    if msg.get("role") == "system":
                        msg["role"] = "user"

            completion_params = {
                'model': self.model,
                'messages': messages,
                'temperature': temperature,
                'max_tokens': max_tokens
            }

            if response_format == 'json':
                completion_params['response_format'] = {'type': 'json_object'}
            
            response = self.client.chat.completions.create(**completion_params)
            return response.choices[0].message.content

        except Exception as e:
            self.logger.error(f"OpenAI API call failed: {e}")
            raise
    
    def call_command_processing_api(self, command: str, current_diagram_data: dict = None) -> str:
        """
        Direct natural language to React Flow JSON conversion.
        
        Args:
            command: Natural language command
            current_diagram_data: Current diagram state with nodes and edges
            
        Returns:
            JSON string with exact React Flow node/edge structures
        """
        try:
            system_prompt = self._build_direct_json_prompt(current_diagram_data)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": command}
            ]

            response = self.call_api(
                messages=messages,
                temperature=0.2,  # Very low for consistent JSON generation
                max_tokens=3000,  # More tokens for complete class definitions
                response_format='json'
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Command processing API call failed: {e}")
            raise
    
    def _build_direct_json_prompt(self, current_diagram_data: dict = None) -> str:
        """
        Build comprehensive prompt for direct React Flow JSON generation.
        """
        import time
        timestamp_ms = int(time.time() * 1000)
        
        base_prompt = f"""
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
