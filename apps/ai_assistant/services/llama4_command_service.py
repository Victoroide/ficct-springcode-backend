"""Llama 4 Maverick Command Service for UML Diagram Generation.

Processes natural language commands using Llama 4 Maverick 17B via AWS Bedrock.
70% cheaper than Nova Pro with excellent reasoning and 1M token context window.

Pricing:
    - Input: $0.24 per 1M tokens
    - Output: $0.97 per 1M tokens
    - Average cost per command: $0.001-0.002
    - Response time: 8-12 seconds
    - Context window: 1M tokens (vs 300K Nova Pro)
"""

import json
import logging
import re
import time
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from django.conf import settings

logger = logging.getLogger(__name__)

_llama4_command_client = None
_cost_tracking = {
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "total_cost_usd": 0.0,
    "commands_processed": 0
}


def get_llama4_command_client():
    """
    Get singleton Llama 4 Maverick client instance for command processing.
    
    Uses boto3 AWS SDK configured for Bedrock with inference profile.
    
    Returns:
        Bedrock runtime client or None if initialization fails
    """
    global _llama4_command_client
    
    if _llama4_command_client is None:
        try:
            _llama4_command_client = boto3.client(
                service_name='bedrock-runtime',
                region_name=settings.AWS_DEFAULT_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
            logger.info("Llama 4 Maverick Bedrock client initialized successfully")
        except (NoCredentialsError, Exception) as e:
            logger.error(f"Failed to initialize Llama 4 Bedrock client: {e}")
            _llama4_command_client = None
    
    return _llama4_command_client


class Llama4CommandService:
    """
    Service for processing UML commands using Llama 4 Maverick 17B via AWS Bedrock.
    
    Features:
        - 70% cheaper than Nova Pro
        - 1M token context window
        - Excellent reasoning capabilities
        - No streaming support (synchronous only)
        - Uses inference profile for cross-region routing
    """
    
    MODEL_ID = "us.meta.llama4-maverick-17b-instruct-v1:0"
    
    INPUT_COST_PER_1M_TOKENS = 0.24
    OUTPUT_COST_PER_1M_TOKENS = 0.97
    
    def __init__(self):
        """Initialize Llama 4 Maverick command service."""
        self.client = get_llama4_command_client()
        self.logger = logging.getLogger(__name__)
    
    def process_command(
        self,
        command: str,
        diagram_id: Optional[str] = None,
        current_diagram_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Process natural language command using Llama 4 Maverick.
        
        Args:
            command: Natural language command in Spanish/English/French
            diagram_id: Optional diagram ID for context
            current_diagram_data: Current diagram state with nodes and edges
            
        Returns:
            Dict with action, elements, confidence, interpretation, metadata
            
        Raises:
            AWSBedrockError: If API call fails
        """
        start_time = time.time()
        
        if not self.client:
            return {
                'action': 'error',
                'elements': [],
                'confidence': 0.0,
                'interpretation': 'Llama 4 Maverick service not configured',
                'error': 'AWS Bedrock service unavailable. Check AWS credentials.',
                'suggestion': 'Configure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in settings.'
            }
        
        try:
            base_prompt = self._build_command_prompt(command, current_diagram_data)
            formatted_prompt = self._format_llama_prompt(base_prompt)
            
            logger.info(f"Calling Llama 4 Maverick API for command: {command[:100]}")
            
            request_body = {
                "prompt": formatted_prompt,
                "max_gen_len": 6000,
                "temperature": 0.1,
                "top_p": 0.9
            }
            
            response = self.client.invoke_model(
                modelId=self.MODEL_ID,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json"
            )
            
            response_body = json.loads(response['body'].read())
            
            generation = response_body.get('generation', '')
            prompt_tokens = response_body.get('prompt_token_count', 0)
            completion_tokens = response_body.get('generation_token_count', 0)
            stop_reason = response_body.get('stop_reason', 'unknown')
            
            logger.info(f"Llama 4 response body keys: {response_body.keys()}")
            logger.info(f"Generation field length: {len(generation)} chars")
            logger.info(f"Generation preview: {generation[:300]}")
            
            if not generation:
                logger.error(f"Empty generation field! Full response body: {response_body}")
                return {
                    'action': 'error',
                    'elements': [],
                    'confidence': 0.0,
                    'interpretation': 'Llama 4 returned empty generation',
                    'error': 'Empty response from model',
                    'metadata': {
                        'model': 'llama4-maverick',
                        'response_time': round(time.time() - start_time, 2),
                        'error_occurred': True
                    }
                }
            
            cost_info = self._calculate_cost(prompt_tokens, completion_tokens)
            
            processing_time = time.time() - start_time
            
            result = self._parse_response(generation)
            
            # CRITICAL: Validate elements array is not empty
            if not result.get('elements') or len(result.get('elements', [])) == 0:
                logger.error("[CRITICAL] Llama 4 returned EMPTY elements array")
                logger.error(f"[CRITICAL] Full generation text (first 1000 chars): {generation[:1000]}")
                logger.error(f"[CRITICAL] Full generation text (last 500 chars): {generation[-500:]}")
                logger.error(f"[CRITICAL] Parsed result: {result}")
                
                # Return error to trigger fallback
                return {
                    'action': 'error',
                    'elements': [],
                    'confidence': 0.0,
                    'interpretation': 'Llama 4 returned empty elements array',
                    'error': 'Empty elements array - fallback required',
                    'metadata': {
                        'model': 'llama4-maverick',
                        'response_time': round(time.time() - start_time, 2),
                        'error_occurred': True,
                        'error_reason': 'empty_elements_array',
                        'requires_fallback': True
                    }
                }
            
            logger.info(f"[SUCCESS] Llama 4 generated {len(result['elements'])} elements")
            
            result['metadata'] = {
                'model': 'llama4-maverick',
                'response_time': round(processing_time, 2),
                'input_tokens': prompt_tokens,
                'output_tokens': completion_tokens,
                'cost_usd': cost_info['total_cost'],
                'stop_reason': stop_reason
            }
            
            self.logger.info(
                f"Llama 4 Maverick processed command in {processing_time:.2f}s. "
                f"Tokens: {prompt_tokens} in + {completion_tokens} out. "
                f"Cost: ${cost_info['total_cost']:.6f}"
            )
            
            return result
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            self.logger.error(
                f"Llama 4 Maverick API error: {error_code} - {error_message}",
                exc_info=True
            )
            
            processing_time = time.time() - start_time
            
            return {
                'action': 'error',
                'elements': [],
                'confidence': 0.0,
                'interpretation': f'Llama 4 Maverick API error: {error_code}',
                'error': 'Failed to process command with Llama 4 Maverick.',
                'suggestion': 'The system will automatically try Nova Pro as fallback.',
                'metadata': {
                    'model': 'llama4-maverick',
                    'response_time': round(processing_time, 2),
                    'error_occurred': True,
                    'error_code': error_code
                }
            }
        except Exception as e:
            self.logger.error(f"Unexpected error in Llama 4 Maverick processing: {e}", exc_info=True)
            
            processing_time = time.time() - start_time
            
            return {
                'action': 'error',
                'elements': [],
                'confidence': 0.0,
                'interpretation': 'Unexpected error during command processing',
                'error': str(e),
                'suggestion': 'Please try rephrasing your command or contact support.',
                'metadata': {
                    'model': 'llama4-maverick',
                    'response_time': round(processing_time, 2),
                    'error_occurred': True
                }
            }
    
    def _build_command_prompt(self, command: str, current_diagram_data: Optional[Dict] = None) -> str:
        """
        Build comprehensive prompt for command processing using advanced prompt engineering.
        
        This prompt architecture applies cognitive scaffolding techniques optimized for
        Llama 4 Maverick's mixture-of-experts architecture to elicit proper reasoning
        about database relationships and domain modeling.
        
        Key techniques employed:
        - Persona priming (database architect role)
        - Step-by-step reasoning framework
        - Domain knowledge injection
        - Anti-pattern warnings
        - Self-validation checkpoints
        - Few-shot learning with explanations
        
        Args:
            command: Natural language command
            current_diagram_data: Optional existing diagram data
            
        Returns:
            Formatted prompt string with complete diagram context and reasoning framework
        """
        import time
        timestamp_ms = int(time.time() * 1000)
        
        base_prompt = f"""═══════════════════════════════════════════════════════════════════
ROLE ASSIGNMENT: You are a Senior Database Architect
═══════════════════════════════════════════════════════════════════

You have 15 years of experience in normalized database design, specializing in 
business systems, e-commerce, and enterprise applications. Your expertise includes:
- Domain-driven design principles
- Entity relationship modeling with proper cardinality
- Third normal form (3NF) database architecture
- JPA/Hibernate entity design for Spring Boot applications

Your task is to design production-quality database schemas that reflect real-world
business logic, not simplified toy examples.

═══════════════════════════════════════════════════════════════════
CRITICAL ANTI-PATTERN WARNING
═══════════════════════════════════════════════════════════════════

WARNING: DO NOT default all relationships to 1:1 (one-to-one)
WARNING: This is the most common error in database design
WARNING: Real systems have complex relationships:
   - 1:many (Customer has many Orders) - MOST COMMON
   - many:many (Student enrolls in many Courses, Course has many Students)
   - 1:1 (User has one Profile) - RARE, needs justification

Before modeling any relationship, ask yourself:
"Can one instance of Entity A relate to MULTIPLE instances of Entity B?"

If YES → You need 1:many or many:many relationship

═══════════════════════════════════════════════════════════════════
STEP-BY-STEP REASONING FRAMEWORK
═══════════════════════════════════════════════════════════════════

PHASE 1: IDENTIFY ALL ENTITIES
- What are the main business objects in this domain?
- What data needs to be stored and tracked?
- Which concepts deserve their own table?

PHASE 2: DETERMINE CARDINALITY FOR EACH RELATIONSHIP
For every potential relationship between Entity A and Entity B:

Question Set A (A → B direction):
Q1: Can ONE instance of A exist with ZERO instances of B? (optional relationship?)
Q2: Can ONE instance of A relate to exactly ONE instance of B?
Q3: Can ONE instance of A relate to MANY instances of B? ← KEY QUESTION

Question Set B (B → A direction):
Q4: Can ONE instance of B exist with ZERO instances of A? (optional relationship?)
Q5: Can ONE instance of B relate to exactly ONE instance of A?
Q6: Can ONE instance of B relate to MANY instances of A? ← KEY QUESTION

DECISION MATRIX:
- If Q3=NO and Q6=NO → One-to-One (1:1) - RARE
- If Q3=YES and Q6=NO → One-to-Many (1:*) - COMMON
- If Q3=NO and Q6=YES → Many-to-One (*:1) - COMMON
- If Q3=YES and Q6=YES → Many-to-Many (*:*) - Requires junction table

PHASE 3: VALIDATE WITH BUSINESS SCENARIOS
For each relationship, create a concrete example:
- "Customer #42 places Order #101 on Monday"
- "Customer #42 places Order #102 on Tuesday"
- Conclusion: Customer (1) → (*) Order [one customer, many orders]

PHASE 4: CHECK REFERENTIAL INTEGRITY
- If Entity A is deleted, what happens to Entity B?
- Does Entity B require Entity A to exist?
- Should deletion cascade, set null, or be restricted?

═══════════════════════════════════════════════════════════════════
DOMAIN-SPECIFIC RELATIONSHIP PATTERNS
═══════════════════════════════════════════════════════════════════

PATTERN 1: SALES/TRANSACTION SYSTEMS (e-commerce, retail, shops):
Pattern: Customer → Order (1:*), Order → OrderDetail (1:*), Product ↔ Order (*:* via OrderDetail)

Example entities: Customer, Order, Product, OrderDetail (junction table)
Key relationships:
- Customer (1) → (*) Order - customers place multiple orders over time
- Order (1) → (*) OrderDetail - each order contains multiple items
- Product (1) → (*) OrderDetail - products appear in many orders
- Order (*) ↔ (*) Product - many-to-many via OrderDetail junction table

Business rules:
- Customer returns weekly → multiple orders per customer
- Each order has multiple products → one-to-many
- Same product sold repeatedly → product appears in many order details
- OrderDetail links Order + Product + quantity + price

PATTERN 2: INVENTORY MANAGEMENT:
Pattern: Product (1) ↔ (1) Inventory, Location (1) → (*) Inventory

Example: Warehouse tracking
- Product (1) → (1) Inventory - each product has one inventory record
- Location (1) → (*) Inventory - warehouses track many products
- Inventory (1) → (*) Transaction - track all stock changes

PATTERN 3: USER/CONTENT SYSTEMS (social media, blogs):
Pattern: User (1) → (*) Post, Post (1) → (*) Comment, User ↔ Post (*:* for likes)

Example: Blog platform
- User (1) → (*) Post - users create multiple posts
- Post (1) → (*) Comment - posts have many comments
- User (1) → (*) Comment - users write many comments
- User (*) ↔ (*) Post - users can like many posts (needs Like junction table)

PATTERN 4: BOOKING/SCHEDULING SYSTEMS:
Pattern: Customer (1) → (*) Booking, Resource (1) → (*) Booking

Example: Hotel reservation
- Customer (1) → (*) Booking - customers make multiple reservations
- Room (1) → (*) Booking - rooms booked multiple times
- TimeSlot (1) → (1) Booking - each time slot has one booking

═══════════════════════════════════════════════════════════════════
COMPLETE WORKING EXAMPLE WITH RELATIONSHIPS
═══════════════════════════════════════════════════════════════════

Command: "create database for ice cream shop"

REASONING PROCESS:

Step 1 - Identify Entities:
- Customer (who buys ice cream)
- Product (ice cream flavors, toppings)
- Sale (purchase transaction)
- SaleDetail (junction table for Sale + Product)
- Inventory (stock tracking)

Step 2 - Determine Relationships:

Relationship A: Customer → Sale
Q: Can one customer make many sales? YES (customers return repeatedly)
Q: Can one sale belong to many customers? NO (one receipt per customer)
Decision: Customer (1) → (*) Sale [ONE-TO-MANY]
Justification: Customer #42 buys ice cream Monday, Tuesday, Friday = 3 sales

Relationship B: Sale → SaleDetail
Q: Can one sale have many line items? YES (customer buys 2 scoops + topping)
Q: Can one line item belong to many sales? NO (each line is for one receipt)
Decision: Sale (1) → (*) SaleDetail [ONE-TO-MANY]
Justification: Sale #101 contains: vanilla scoop + chocolate scoop + cherry topping

Relationship C: Product → SaleDetail
Q: Can one product appear in many sales? YES (vanilla sold to many customers)
Q: Can one sale detail reference many products? NO (each line = one product + quantity)
Decision: Product (1) → (*) SaleDetail [ONE-TO-MANY]
Note: This creates (*:*) relationship between Product and Sale via SaleDetail junction

Relationship D: Product → Inventory
Q: Can one product have many inventory records? NO (one stock counter per product)
Q: Can one inventory record track many products? NO (one record per product)
Decision: Product (1) → (1) Inventory [ONE-TO-ONE]
Justification: Each product has exactly one current stock quantity

Step 3 - Business Validation:
[VALID] Customer can purchase multiple times
[VALID] Each sale can contain multiple products
[VALID] Same product (vanilla) appears in many sales
[VALID] Inventory updates when sales occur
[VALID] SaleDetail tracks product + quantity + unit price for each line item

CARDINALITY SUMMARY:
- 60% are ONE-TO-MANY (Customer→Sale, Sale→SaleDetail, Product→SaleDetail)
- 20% are ONE-TO-ONE (Product→Inventory)
- 20% are implied MANY-TO-MANY (Product↔Sale via SaleDetail junction)
- 0% are unjustified ONE-TO-ONE relationships [CORRECT]

═══════════════════════════════════════════════════════════════════
JSON OUTPUT FORMAT SPECIFICATION
═══════════════════════════════════════════════════════════════════

REQUIRED: Return ONLY valid JSON. No explanatory text. No markdown. No code blocks.

STRUCTURE FOR NEW DIAGRAM (action: "create_class"):
{{
  "action": "create_class",
  "elements": [
    {{
      "type": "node",
      "data": {{
        "id": "class-{timestamp_ms}-1",
        "data": {{
          "label": "EntityName",
          "nodeType": "class",
          "isAbstract": false,
          "attributes": [
            {{
              "id": "attr-1-1",
              "name": "id",
              "type": "Long",
              "visibility": "private",
              "isStatic": false,
              "isFinal": false
            }},
            {{
              "id": "attr-1-2",
              "name": "attributeName",
              "type": "String",
              "visibility": "private",
              "isStatic": false,
              "isFinal": false
            }}
          ],
          "methods": []
        }},
        "position": {{"x": 100, "y": 100}}
      }}
    }}
  ],
  "confidence": 0.95,
  "interpretation": "Created N entities with proper relationships for [domain]"
}}

STRUCTURE FOR RELATIONSHIPS (action: "create_relationship"):
{{
  "action": "create_relationship",
  "elements": [
    {{
      "type": "edge",
      "data": {{
        "source": "class-{timestamp_ms}-1",
        "target": "class-{timestamp_ms}-2",
        "relationshipType": "ASSOCIATION",
        "sourceMultiplicity": "1",
        "targetMultiplicity": "*",
        "label": "has"
      }}
    }}
  ],
  "confidence": 0.95,
  "interpretation": "Created relationship: Source (1) → (*) Target"
}}

RELATIONSHIP TYPES:
- ASSOCIATION: General relationship with cardinality
- AGGREGATION: Weak containment (has-a, can exist independently)
- COMPOSITION: Strong containment (part-of, cannot exist independently)
- INHERITANCE: IS-A relationship (extends/implements)
- DEPENDENCY: Uses relationship (temporary association)

MULTIPLICITY NOTATION:
- "1" = exactly one
- "0..1" = zero or one (optional)
- "*" or "0..*" = zero or many
- "1..*" = one or many (at least one required)

TYPE MAPPINGS FOR ATTRIBUTES:
- id, codigo, code → Long
- nombre, name, titulo, title → String
- cantidad, stock, age → Integer
- precio, cost, amount → Double
- activo, enabled → Boolean
- fecha, date, timestamp → Date

POSITIONING STRATEGY:
- Entity 1: (100, 100)
- Entity 2: (400, 100)
- Entity 3: (700, 100)
- Entity 4: (100, 400)
- Entity 5: (400, 400)
- Increment x by 300, y by 300 for each row

═══════════════════════════════════════════════════════════════════
SELF-VALIDATION CHECKLIST (BEFORE GENERATING JSON)
═══════════════════════════════════════════════════════════════════

Before outputting JSON, verify:

CHECKPOINT - Entity Identification:
  [ ] All business concepts represented as entities?
  [ ] Each entity has clear purpose and responsibility?
  [ ] Entity names are singular nouns (Customer, not Customers)?

CHECKPOINT - Attribute Completeness:
  [ ] Each entity has at least 3 attributes?
  [ ] Every entity has an "id" field (type: Long)?
  [ ] Attribute types match data (String, Long, Integer, Double, Date, Boolean)?
  [ ] All attributes have visibility (private for fields)?

CHECKPOINT - Relationship Correctness:
  [ ] Did I question default assumptions about cardinality?
  [ ] Are less than 20% of relationships 1:1? (should be rare)
  [ ] Are most relationships 1:many or many:many? (realistic)
  [ ] Can I explain each cardinality with a business scenario?

CHECKPOINT - Normalization:
  [ ] No repeated groups in entities?
  [ ] Many-to-many relationships use junction tables?
  [ ] Foreign keys will prevent orphan records?

CHECKPOINT - Production Readiness:
  [ ] Schema supports real business operations?
  [ ] Entities can be mapped to JPA/Hibernate?
  [ ] Design allows for typical CRUD operations?

═══════════════════════════════════════════════════════════════════
OUTPUT REQUIREMENTS
═══════════════════════════════════════════════════════════════════

CRITICAL: Elements array MUST NOT be empty
Minimum: 1 class for simple commands
Typical: 3-6 classes for database/system commands
Include: At least 3 attributes per class
Format: Start response with {{ and end with }}
Content: ONLY JSON, no explanations, no markdown, no code blocks

SUPPORTED ACTIONS:
- create_class: Generate new entities (use for new diagrams)
- update_class: Modify existing entity (use when context provided)
- create_relationship: Add edge between entities
"""
        
        if current_diagram_data:
            nodes = current_diagram_data.get('nodes', [])
            edges = current_diagram_data.get('edges', [])
            
            if nodes:
                context = "\n\n" + "="*70 + "\n"
                context += "EXISTING DIAGRAM CONTEXT\n"
                context += "="*70 + "\n\n"
                context += f"Total Classes: {len(nodes)}\n"
                context += f"Total Relationships: {len(edges)}\n\n"
                context += "CLASSES DETAIL:\n\n"
                
                for idx, node in enumerate(nodes, 1):
                    node_id = node.get('id', 'unknown')
                    data = node.get('data', {})
                    label = data.get('label', 'Unknown')
                    position = node.get('position', {'x': 0, 'y': 0})
                    attributes = data.get('attributes', [])
                    methods = data.get('methods', [])
                    node_type = data.get('nodeType', 'class')
                    is_abstract = data.get('isAbstract', False)
                    
                    context += f"{idx}. {label} (ID: {node_id})\n"
                    if is_abstract:
                        context += "   Type: Abstract Class\n"
                    context += f"   Position: x={position['x']}, y={position['y']}\n"
                    
                    if attributes:
                        context += "   Attributes:\n"
                        for attr in attributes:
                            attr_name = attr.get('name', 'unknown')
                            attr_type = attr.get('type', 'String')
                            visibility = attr.get('visibility', 'private')
                            is_static = attr.get('isStatic', False)
                            is_final = attr.get('isFinal', False)
                            modifiers = []
                            if is_static:
                                modifiers.append('static')
                            if is_final:
                                modifiers.append('final')
                            mod_str = ' '.join(modifiers)
                            context += f"   - {attr_name}: {attr_type} ({visibility})"
                            if mod_str:
                                context += f" [{mod_str}]"
                            context += "\n"
                    else:
                        context += "   Attributes: (none)\n"
                    
                    if methods:
                        context += "   Methods:\n"
                        for method in methods:
                            method_name = method.get('name', 'unknown')
                            return_type = method.get('returnType', 'void')
                            visibility = method.get('visibility', 'public')
                            parameters = method.get('parameters', [])
                            if parameters:
                                param_str = ', '.join([f"{p.get('name', 'param')}: {p.get('type', 'String')}" for p in parameters])
                                context += f"   - {method_name}({param_str}): {return_type} ({visibility})\n"
                            else:
                                context += f"   - {method_name}(): {return_type} ({visibility})\n"
                    else:
                        context += "   Methods: (none)\n"
                    
                    context += "\n"
                
                if edges:
                    context += "RELATIONSHIPS:\n\n"
                    for idx, edge in enumerate(edges, 1):
                        source_id = edge.get('source', '')
                        target_id = edge.get('target', '')
                        edge_data = edge.get('data', {})
                        rel_type = edge_data.get('relationshipType', 'ASSOCIATION')
                        source_mult = edge_data.get('sourceMultiplicity', '1')
                        target_mult = edge_data.get('targetMultiplicity', '1')
                        label = edge_data.get('label', '')
                        
                        source_name = next((n['data']['label'] for n in nodes if n['id'] == source_id), source_id)
                        target_name = next((n['data']['label'] for n in nodes if n['id'] == target_id), target_id)
                        
                        context += f"{idx}. {source_name} → {target_name} ({rel_type})\n"
                        context += f"   Source ID: {source_id}\n"
                        context += f"   Target ID: {target_id}\n"
                        context += f"   Source Multiplicity: {source_mult}\n"
                        context += f"   Target Multiplicity: {target_mult}\n"
                        if label:
                            context += f"   Label: {label}\n"
                        context += "\n"
                else:
                    context += "RELATIONSHIPS: (none)\n\n"
                
                context += "="*70 + "\n"
                context += "CRITICAL INSTRUCTIONS FOR THIS COMMAND\n"
                context += "="*70 + "\n\n"
                
                context += "1. IDENTIFY THE TARGET:\n"
                context += "   - Find class by exact name match from context above\n"
                context += "   - Use the class ID from context (NEVER create new ID for existing class)\n"
                context += "   - Do NOT create duplicate classes\n\n"
                
                context += "2. MODIFICATION OPERATIONS:\n"
                context += "   - ADD ATTRIBUTE: Use action 'update_class', include ALL existing attributes + new one\n"
                context += "   - REMOVE ATTRIBUTE: Use action 'update_class', include all EXCEPT removed attribute\n"
                context += "   - MODIFY ATTRIBUTE: Use action 'update_class', update the specific attribute\n"
                context += "   - ADD METHOD: Use action 'update_class', include ALL existing methods + new one\n"
                context += "   - REMOVE METHOD: Use action 'update_class', include all EXCEPT removed method\n\n"
                
                context += "3. RELATIONSHIP OPERATIONS:\n"
                context += "   - Use action 'create_relationship'\n"
                context += "   - Use EXISTING class IDs from context for source and target\n"
                context += "   - Never create classes just to make relationships\n\n"
                
                context += "4. PRESERVATION RULES:\n"
                context += "   - When updating a class, include ALL its current attributes\n"
                context += "   - Keep class position exactly as shown in context\n"
                context += "   - Keep same class ID\n"
                context += "   - Only change what the command explicitly requests\n\n"
                
                context += "5. JSON FORMAT FOR UPDATE:\n"
                context += '{{\n'
                context += '  "action": "update_class",\n'
                context += '  "elements": [{{\n'
                context += '    "type": "node",\n'
                context += '    "data": {{\n'
                context += '      "id": "class-xxx",\n'
                context += '      "data": {{\n'
                context += '        "label": "ClassName",\n'
                context += '        "attributes": [],\n'
                context += '        "methods": [],\n'
                context += '        "nodeType": "class"\n'
                context += '      }},\n'
                context += '      "position": {{"x": same, "y": same}}\n'
                context += '    }}\n'
                context += '  }}],\n'
                context += '  "confidence": 0.95,\n'
                context += '  "interpretation": "Updated ClassName..."\n'
                context += '}}\n\n'
                
                base_prompt += context
        else:
            base_prompt += "\n\nNo existing diagram context. Creating new diagram from scratch.\n\n"
        
        base_prompt += f"\n\n{'═'*70}\n"
        base_prompt += "YOUR COMMAND TO PROCESS\n"
        base_prompt += f"{'═'*70}\n\n"
        base_prompt += f'"{command}"\n\n'
        
        base_prompt += f"{'═'*70}\n"
        base_prompt += "REASONING PROTOCOL (COMPLETE BEFORE GENERATING JSON)\n"
        base_prompt += f"{'═'*70}\n\n"
        
        base_prompt += "Step 1: IDENTIFY DOMAIN\n"
        base_prompt += "What is the business domain? (e-commerce, social media, booking, etc.)\n"
        base_prompt += "What are the key business processes?\n\n"
        
        base_prompt += "Step 2: LIST ENTITIES\n"
        base_prompt += "What are ALL the entities needed for this domain?\n"
        base_prompt += "Minimum 3-5 entities for database systems\n"
        base_prompt += "Each entity represents a business concept\n\n"
        
        base_prompt += "Step 3: DETERMINE RELATIONSHIPS\n"
        base_prompt += "For EACH pair of entities, apply the cardinality questions:\n"
        base_prompt += "- Can ONE A relate to MANY B? (If YES → 1:many or many:many)\n"
        base_prompt += "- Can ONE B relate to MANY A? (If YES → many:1 or many:many)\n"
        base_prompt += "- If both YES → many:many (needs junction table)\n\n"
        
        base_prompt += "Step 4: VALIDATE BUSINESS LOGIC\n"
        base_prompt += "Create a concrete scenario for each relationship\n"
        base_prompt += "Example: 'Customer #42 places multiple orders = 1:many'\n\n"
        
        base_prompt += "Step 5: VERIFY CARDINALITY DISTRIBUTION\n"
        base_prompt += "Check: Are most relationships 1:many? (Should be 50-70%)\n"
        base_prompt += "Check: Are 1:1 relationships rare? (Should be < 20%)\n"
        base_prompt += "Check: Are many:many using junction tables?\n\n"
        
        base_prompt += f"{'═'*70}\n"
        base_prompt += "JSON GENERATION REQUIREMENTS (NO EXCEPTIONS)\n"
        base_prompt += f"{'═'*70}\n\n"
        
        base_prompt += "REQUIREMENT 1: MINIMUM ENTITY COUNT\n"
        base_prompt += "   - Simple commands: AT LEAST 1-2 entities\n"
        base_prompt += "   - Database/system commands: AT LEAST 3-5 entities\n"
        base_prompt += "   - Complex systems: 5-8 entities\n\n"
        
        base_prompt += "REQUIREMENT 2: ATTRIBUTES PER ENTITY\n"
        base_prompt += "   - MINIMUM 3 attributes per entity\n"
        base_prompt += "   - Always include: id (Long)\n"
        base_prompt += "   - Always include: name/title field (String)\n"
        base_prompt += "   - Add 1-3 domain-specific attributes\n\n"
        
        base_prompt += "REQUIREMENT 3: UNIQUE IDENTIFIERS\n"
        base_prompt += f"   - Use timestamp-based IDs: class-{timestamp_ms}-1, class-{timestamp_ms}-2, etc.\n"
        base_prompt += "   - Attribute IDs: attr-{class_num}-{attr_num}\n"
        base_prompt += "   - Ensure ALL IDs are unique\n\n"
        
        base_prompt += "REQUIREMENT 4: POSITIONING\n"
        base_prompt += "   - Entity 1: (100, 100)\n"
        base_prompt += "   - Entity 2: (400, 100)\n"
        base_prompt += "   - Entity 3: (700, 100)\n"
        base_prompt += "   - Entity 4: (100, 400) - new row\n"
        base_prompt += "   - Increment x by 300, y by 300\n\n"
        
        base_prompt += "REQUIREMENT 5: JSON FORMAT (CRITICAL)\n"
        base_prompt += "   [NO] NO explanatory text before JSON\n"
        base_prompt += "   [NO] NO explanatory text after JSON\n"
        base_prompt += "   [NO] NO markdown code blocks (```json)\n"
        base_prompt += "   [NO] NO comments inside JSON\n"
        base_prompt += "   [YES] ONLY valid JSON object\n"
        base_prompt += "   [YES] Start with {{ immediately\n"
        base_prompt += "   [YES] End with }} immediately\n\n"
        
        base_prompt += f"{'═'*70}\n"
        base_prompt += "CONSTRAINT-BASED VALIDATION\n"
        base_prompt += f"{'═'*70}\n\n"
        
        base_prompt += "Before returning JSON, verify these constraints:\n\n"
        
        base_prompt += "CONSTRAINT 1: Elements array MUST have at least 1 element\n"
        base_prompt += "  Verification: len(elements) >= 1\n\n"
        
        base_prompt += "CONSTRAINT 2: Each element MUST have all required fields\n"
        base_prompt += '  Verification: "type", "data" with nested "id", "data", "position"\n\n'
        
        base_prompt += "CONSTRAINT 3: Each entity MUST have at least 3 attributes\n"
        base_prompt += "  Verification: len(attributes) >= 3 for each class\n\n"
        
        base_prompt += "CONSTRAINT 4: Cardinality distribution MUST be realistic\n"
        base_prompt += "  Verification: 1:many > 50%, 1:1 < 20%, many:many with junction\n\n"
        
        base_prompt += "CONSTRAINT 5: JSON MUST be valid and parseable\n"
        base_prompt += "  Verification: No trailing commas, proper quotes, valid structure\n\n"
        
        base_prompt += f"{'═'*70}\n"
        base_prompt += "GENERATE JSON NOW\n"
        base_prompt += f"{'═'*70}\n\n"
        
        base_prompt += "Following the reasoning protocol and constraints above:\n"
        base_prompt += "1. Apply domain knowledge from patterns section\n"
        base_prompt += "2. Generate entities with proper attributes\n"
        base_prompt += "3. Ensure realistic cardinality (NOT all 1:1)\n"
        base_prompt += "4. Return ONLY the JSON object\n"
        base_prompt += "5. NO text before {{\n"
        base_prompt += "6. NO text after }}\n"
        base_prompt += "7. Start your response with {{ immediately\n\n"
        
        base_prompt += "BEGIN JSON OUTPUT:"
        
        return base_prompt
    
    def _format_llama_prompt(self, base_prompt: str) -> str:
        """
        Format prompt in Llama 4 Maverick specific format with JSON priming.
        
        Llama 4 requires special tokens for proper processing:
        - <|begin_of_text|> at start
        - <|start_header_id|>user<|end_header_id|> for user role
        - <|eot_id|> for end of turn
        - <|start_header_id|>assistant<|end_header_id|> for assistant role
        - Prime with {{ to start JSON generation immediately
        
        Args:
            base_prompt: The base prompt content
            
        Returns:
            Formatted prompt with Llama 4 tokens
        """
        formatted = "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n"
        formatted += base_prompt
        formatted += "\n<|eot_id|>\n<|start_header_id|>assistant<|end_header_id|>\n{{"
        
        return formatted
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse Llama 4 Maverick response text and extract JSON.
        
        Uses multiple extraction strategies to handle various response formats.
        Ensures all required fields are present with proper defaults.
        
        Args:
            response_text: Raw response text from Llama 4 Maverick
            
        Returns:
            Parsed JSON as dictionary with all required fields
        """
        logger.info(f"[PARSING] Starting parse of {len(response_text)} char response")
        logger.info(f"[PARSING] Response preview (first 400 chars): {response_text[:400]}")
        logger.info(f"[PARSING] Response preview (last 200 chars): {response_text[-200:]}")
        
        if not response_text or not response_text.strip():
            logger.error("[PARSING] Empty response text")
            return {
                'action': 'error',
                'elements': [],
                'confidence': 0.0,
                'interpretation': 'Empty response from Llama 4 Maverick',
                'error': 'No output generated'
            }
        
        strategies = [
            self._try_direct_parse,
            self._try_markdown_extraction,
            self._try_brace_counting,
            self._try_json_block_extraction,
            self._try_last_valid_json
        ]
        
        for i, strategy in enumerate(strategies, 1):
            try:
                logger.info(f"[PARSING] Trying strategy {i}/{len(strategies)}: {strategy.__name__}")
                result = strategy(response_text)
                if result:
                    logger.info(f"[PARSING] Strategy {strategy.__name__} SUCCESS")
                    logger.info(f"[PARSING] Extracted keys: {result.keys()}")
                    logger.info(f"[PARSING] Action: {result.get('action')}")
                    logger.info(f"[PARSING] Elements count: {len(result.get('elements', []))}")
                    
                    validated_result = self._validate_and_normalize_result(result)
                    logger.info(f"[PARSING] After validation - Action: {validated_result.get('action')}, Elements: {len(validated_result.get('elements', []))}")
                    return validated_result
                else:
                    logger.warning(f"[PARSING] Strategy {strategy.__name__} returned None")
            except Exception as e:
                logger.warning(f"[PARSING] Strategy {strategy.__name__} failed with error: {e}")
                continue
        
        logger.error(f"[PARSING] ALL {len(strategies)} STRATEGIES FAILED")
        logger.error(f"[PARSING] Full response text:\n{response_text}")
        
        return {
            'action': 'error',
            'elements': [],
            'confidence': 0.0,
            'interpretation': 'Could not parse Llama 4 Maverick response',
            'error': 'Failed to extract valid JSON from all strategies',
            'raw_response_preview': response_text[:500]
        }
    
    def _validate_and_normalize_result(self, result: Dict) -> Dict[str, Any]:
        """
        Validate and normalize parsed result to ensure all required fields exist.
        
        Args:
            result: Raw parsed result from extraction strategy
            
        Returns:
            Normalized result with all required fields and proper defaults
        """
        if not isinstance(result, dict):
            logger.error(f"[VALIDATION] Result is not a dict: {type(result)}")
            return {
                'action': 'error',
                'elements': [],
                'confidence': 0.0,
                'interpretation': 'Invalid result type',
                'error': 'Parsed result is not a dictionary'
            }
        
        normalized = {
            'action': result.get('action', 'create_class'),
            'elements': result.get('elements', []),
            'confidence': result.get('confidence', 0.85),
            'interpretation': result.get('interpretation', 'Generated by Llama 4 Maverick')
        }
        
        if not normalized['action']:
            logger.warning("[VALIDATION] Missing action, defaulting to 'create_class'")
            normalized['action'] = 'create_class'
        
        if not isinstance(normalized['elements'], list):
            logger.warning(f"[VALIDATION] Elements not a list: {type(normalized['elements'])}, defaulting to []")
            normalized['elements'] = []
        
        if not isinstance(normalized['confidence'], (int, float)):
            logger.warning(f"[VALIDATION] Confidence not numeric: {type(normalized['confidence'])}, defaulting to 0.85")
            normalized['confidence'] = 0.85
        
        if not isinstance(normalized['interpretation'], str):
            logger.warning(f"[VALIDATION] Interpretation not string: {type(normalized['interpretation'])}, defaulting")
            normalized['interpretation'] = 'Generated by Llama 4 Maverick'
        
        logger.info(f"[VALIDATION] Normalized result: action={normalized['action']}, elements={len(normalized['elements'])}, confidence={normalized['confidence']}")
        
        return normalized
    
    def _try_direct_parse(self, text: str) -> Optional[Dict]:
        """Try parsing text directly as JSON."""
        parsed = json.loads(text.strip())
        logger.debug(f"[DIRECT_PARSE] Success: {parsed.keys() if isinstance(parsed, dict) else type(parsed)}")
        return parsed
    
    def _try_markdown_extraction(self, text: str) -> Optional[Dict]:
        """Extract JSON from markdown code blocks."""
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        return None
    
    def _try_brace_counting(self, text: str) -> Optional[Dict]:
        """Extract JSON by finding balanced braces."""
        first_brace = text.find('{')
        if first_brace == -1:
            return None
        
        brace_count = 0
        for i in range(first_brace, len(text)):
            if text[i] == '{':
                brace_count += 1
            elif text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    json_str = text[first_brace:i+1]
                    return json.loads(json_str)
        
        return None
    
    def _try_json_block_extraction(self, text: str) -> Optional[Dict]:
        """Look for JSON block patterns."""
        patterns = [
            r'\{[^{}]*"action"[^{}]*"elements"[^{}]*\}',
            r'\{.*?"action".*?\}',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except:
                    continue
        
        return None
    
    def _try_last_valid_json(self, text: str) -> Optional[Dict]:
        """Find last occurrence of valid JSON object."""
        all_braces = [(m.start(), '{') for m in re.finditer(r'\{', text)]
        all_braces.extend([(m.start(), '}') for m in re.finditer(r'\}', text)])
        all_braces.sort(reverse=True)
        
        for start_pos, char in all_braces:
            if char == '}':
                for other_pos, other_char in all_braces:
                    if other_char == '{' and other_pos < start_pos:
                        try:
                            candidate = text[other_pos:start_pos+1]
                            return json.loads(candidate)
                        except:
                            continue
        
        return None
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> Dict[str, float]:
        """
        Calculate cost for Llama 4 Maverick API usage.
        
        Pricing:
            - Input: $0.24 per 1M tokens
            - Output: $0.97 per 1M tokens
        
        Args:
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            
        Returns:
            Dict with input_cost, output_cost, total_cost
        """
        input_cost = (prompt_tokens / 1_000_000) * self.INPUT_COST_PER_1M_TOKENS
        output_cost = (completion_tokens / 1_000_000) * self.OUTPUT_COST_PER_1M_TOKENS
        total_cost = input_cost + output_cost
        
        global _cost_tracking
        _cost_tracking["total_input_tokens"] += prompt_tokens
        _cost_tracking["total_output_tokens"] += completion_tokens
        _cost_tracking["total_cost_usd"] += total_cost
        _cost_tracking["commands_processed"] += 1
        
        return {
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "total_cost": round(total_cost, 6)
        }
    
    @staticmethod
    def get_cost_tracking() -> Dict[str, Any]:
        """
        Get cumulative cost tracking statistics.
        
        Returns:
            Dict with total tokens, cost, and commands processed
        """
        return _cost_tracking.copy()
