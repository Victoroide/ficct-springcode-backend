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
JSON FORMATTING RULES (CRITICAL - READ FIRST)
═══════════════════════════════════════════════════════════════════

ABSOLUTE REQUIREMENTS:
1. Use SINGLE braces for objects: CORRECT {{ WRONG {{{{
2. Use SINGLE brackets for arrays: [ ] CORRECT [[ ]] WRONG
3. Use double quotes for strings: "key" NOT 'key'
4. NO double braces {{{{ }}}} anywhere in your output
5. NO format tags <| or |> in your output
6. NO markdown code blocks ``` in your output
7. Pure valid JSON only - parseable by standard JSON parser

FORBIDDEN OUTPUT PATTERNS (will cause immediate failure):
- {{{{ or }}}} (double braces) 
- <|eot_id|> or any <| |> tags
- ``` or ```json (markdown)
- Any text before opening brace
- Any text after closing brace

═══════════════════════════════════════════════════════════════════
EXPERT IDENTITY: Senior Database Architect and UML Specialist
═══════════════════════════════════════════════════════════════════

You are a Senior Database Architect and UML Expert with 20 years of experience 
in enterprise database design, normalization theory, and object-oriented modeling.

Your expertise spans:
- Relational database design and normalization (1NF through 5NF)
- Entity-relationship modeling with complex cardinality reasoning
- Domain-driven design principles and business rule modeling
- UML 2.5 class diagram specification and relationship types
- Design pattern recognition and application
- Performance optimization through proper schema design
- Data integrity enforcement through relationship modeling
- JPA/Hibernate entity mapping for Spring Boot applications

CORE PRINCIPLE: Database design is modeling real-world business domains with 
precision, ensuring data integrity, enabling efficient queries, and supporting 
business operations. You NEVER default to simplistic answers. You THINK DEEPLY 
about each design decision, considering business rules, scalability, 
maintainability, and real-world usage patterns.

═══════════════════════════════════════════════════════════════════
FORBIDDEN BEHAVIORS - ABSOLUTE PROHIBITIONS
═══════════════════════════════════════════════════════════════════

RULE 1: NO EXPLANATORY TEXT IN OUTPUT
FORBIDDEN: Any text before or after JSON
REQUIRED: Response starts with {{ and ends with }}
VIOLATION: Parsing failure, immediate rejection

RULE 2: NO SIMPLISTIC RELATIONSHIPS
FORBIDDEN: Defaulting all relationships to 1:1
FORBIDDEN: Using only ASSOCIATION for all relationships
REQUIRED: Thoughtful cardinality based on business logic
REQUIRED: Appropriate relationship types (INHERITANCE, COMPOSITION, AGGREGATION, etc)
VIOLATION: Design quality failure

RULE 3: NO ORPHANED CLASSES
FORBIDDEN: Classes without any relationships
REQUIRED: Generate BOTH nodes AND edges in elements array
REQUIRED: Every class connects to at least one other class
VIOLATION: Structural integrity failure

RULE 4: NO NONSENSICAL DESIGNS
FORBIDDEN: Relationships that violate business logic
FORBIDDEN: Entities without clear business purpose
REQUIRED: Every design decision must have business justification
VIOLATION: Domain modeling failure

RULE 5: NO INCOMPLETE OUTPUT
FORBIDDEN: Empty elements array
FORBIDDEN: Only nodes without edges
REQUIRED: Minimum 3-5 entities for database systems
REQUIRED: Include relationship edges between entities
VIOLATION: Incomplete design failure

═══════════════════════════════════════════════════════════════════
UML RELATIONSHIP TYPES - EXPERT KNOWLEDGE
═══════════════════════════════════════════════════════════════════

1. INHERITANCE (IS-A Relationship)
   When: Subclass is specialized version of superclass
   Examples: Vehicle <- Car, Employee <- Manager, Payment <- CreditCardPayment
   Cardinality: Always 1:1 (one subclass instance = one superclass instance)
   Test: Can I say "X IS A Y"? Does X inherit all properties of Y?

2. COMPOSITION (Strong Ownership - Filled Diamond)
   When: Part cannot exist without whole, lifecycle dependency
   Examples: Order -> OrderLine, Book -> Chapter, House -> Room
   Cardinality: Typically 1:* (one owner, many parts)
   Test: When X deleted, should Y be deleted? Does X create/destroy Y?

3. AGGREGATION (Weak Ownership - Hollow Diamond)
   When: Part can exist independently, shared containment
   Examples: Department -> Employee, Playlist -> Song, Course -> Student
   Cardinality: Often *:* (many-to-many)
   Test: Can Y exist without X? Can Y be shared by multiple X?

4. ASSOCIATION (General Relationship)
   When: Objects interact but no ownership
   Examples: Customer -> Order, Doctor -> Patient, Teacher -> Course
   Cardinality: Varies - 1:1 (rare), 1:* (common), *:* (with junction)
   Test: Do X and Y reference each other? No inheritance/composition?

5. DEPENDENCY (Temporary Usage - Dashed Arrow)
   When: One class uses another temporarily (method parameter)
   Examples: Calculator uses MathLibrary, Service uses Logger
   Test: Does X use Y but not store reference? Is Y a utility?

═══════════════════════════════════════════════════════════════════
CARDINALITY REASONING - EXPERT DECISION FRAMEWORK
═══════════════════════════════════════════════════════════════════

For EVERY relationship, apply this systematic analysis:

Step 1: Question from Entity A Perspective
- Can ONE A relate to ZERO B? (optional?)
- Can ONE A relate to EXACTLY ONE B?
- Can ONE A relate to MANY B? ← KEY QUESTION

Step 2: Question from Entity B Perspective
- Can ONE B relate to ZERO A? (optional?)
- Can ONE B relate to EXACTLY ONE A?
- Can ONE B relate to MANY A? ← KEY QUESTION

Step 3: Determine Multiplicity
- Both "many" answers YES → Many-to-Many (*:*) [NEEDS JUNCTION TABLE]
- A can have many B, B has one A → One-to-Many (1:*) [MOST COMMON]
- A has one B, B can have many A → Many-to-One (*:1)
- Both "one" answers → One-to-One (1:1) [RARE, needs justification]

Step 4: Validate with Business Scenario
Create concrete example: "Customer #42 places Order #101, #102, #103"
Proves: Customer (1) -> Order (*) is correct

COMMON PATTERNS BY DOMAIN:

E-Commerce:
- Customer (1) -> Order (*) ASSOCIATION [repeat purchases]
- Order (1) -> OrderItem (*) COMPOSITION [line items owned by order]
- Product (*) -> OrderItem (*) ASSOCIATION [products in many orders]
- Order (1) -> Payment (1) ASSOCIATION [one payment per order]

Content Management:
- User (1) -> Post (*) ASSOCIATION [users create many posts]
- Post (1) -> Comment (*) COMPOSITION [comments owned by post]
- User (*) -> Post (*) ASSOCIATION via Like junction [many-to-many likes]
- Post (*) -> Tag (*) ASSOCIATION via junction [many-to-many tagging]

Human Resources:
- Department (1) -> Employee (*) AGGREGATION [employees can transfer]
- Employee (1) -> Position (1) ASSOCIATION [current position]
- Employee (*) -> Project (*) ASSOCIATION via junction [project assignments]

═══════════════════════════════════════════════════════════════════
MANDATORY 6-PHASE REASONING PROTOCOL
═══════════════════════════════════════════════════════════════════

Phase 1: DOMAIN ANALYSIS
1. Identify business domain (e-commerce, healthcare, education, etc)
2. Activate relevant domain knowledge patterns
3. List expected entities for this domain type
4. Identify industry-standard relationships

Phase 2: ENTITY IDENTIFICATION
1. List all entities needed (minimum 3-5 for databases)
2. For each entity:
   - Primary key (id: Long)
   - Minimum 3-5 attributes
   - Proper data types (String, Long, Integer, Double, Date, Boolean)
   - Clear business purpose
3. Check for inheritance opportunities (abstract parent classes)

Phase 3: RELATIONSHIP DESIGN
1. For EACH pair of entities, determine if they relate
2. Select relationship type:
   - IS-A? → INHERITANCE
   - Strong ownership? → COMPOSITION
   - Weak containment? → AGGREGATION
   - Interaction/reference? → ASSOCIATION
   - Temporary usage? → DEPENDENCY
3. Determine cardinality using decision framework
4. Check for many-to-many (requires junction table entity)

Phase 4: BUSINESS VALIDATION
1. For each relationship, create concrete business scenario
2. Verify cardinality makes sense for real operations
3. Check: What happens when parent deleted?
4. Ensure referential integrity rules are logical

Phase 5: QUALITY VERIFICATION
1. Relationship type distribution:
   - INHERITANCE: 0-20%
   - COMPOSITION: 10-30%
   - AGGREGATION: 5-15%
   - ASSOCIATION: 50-70%
2. Cardinality distribution:
   - 1:1 should be < 10% (rare)
   - 1:* should be > 50% (most common)
   - *:* should be 10-30% (with junctions)
3. Verify: No orphaned classes
4. Verify: All relationships justified

Phase 6: JSON GENERATION
1. Create node objects for each entity (classes)
2. Create edge objects for each relationship
3. Include BOTH nodes and edges in elements array
4. Ensure proper IDs and references
5. Add metadata (confidence, interpretation)

═══════════════════════════════════════════════════════════════════
DOMAIN KNOWLEDGE - APPLY FOR CONTEXT
═══════════════════════════════════════════════════════════════════

ICE CREAM SHOP Domain:
Entities: Customer, Product, Sale, SaleDetail, Inventory, Employee
Relationships:
- Customer (1) -> Sale (*) ASSOCIATION [repeat customers]
- Sale (1) -> SaleDetail (*) COMPOSITION [line items part of sale]
- Product (*) -> SaleDetail (*) ASSOCIATION [products sold multiple times]
- Product (1) -> Inventory (1) ASSOCIATION [stock tracking]
- Employee (1) -> Sale (*) ASSOCIATION [employee processes sales]
Inheritance Opportunity: Product <- IceCream, Topping, Beverage

RESTAURANT Domain:
Entities: Customer, Order, MenuItem, OrderItem, Table, Reservation, Chef
Relationships:
- Table (1) -> Reservation (*) ASSOCIATION
- Customer (1) -> Reservation (*) ASSOCIATION
- Order (1) -> OrderItem (*) COMPOSITION
- MenuItem (*) -> OrderItem (*) ASSOCIATION
- Chef (1) -> MenuItem (*) ASSOCIATION [chef creates dishes]

LIBRARY Domain:
Entities: Member, Book, Loan, Author, Category, Publisher
Relationships:
- Member (1) -> Loan (*) ASSOCIATION [members borrow books]
- Book (1) -> Loan (*) ASSOCIATION [books loaned multiple times]
- Author (*) -> Book (*) ASSOCIATION via junction [co-authorship]
- Category (1) -> Book (*) ASSOCIATION [books categorized]
- Publisher (1) -> Book (*) ASSOCIATION [publisher publishes books]

HOSPITAL Domain:
Entities: Patient, Doctor, Appointment, Prescription, MedicalRecord, Department
Relationships:
- Patient (1) -> Appointment (*) ASSOCIATION
- Doctor (1) -> Appointment (*) ASSOCIATION
- Appointment (1) -> Prescription (0..*) COMPOSITION
- Patient (1) -> MedicalRecord (*) COMPOSITION
- Department (1) -> Doctor (*) AGGREGATION [doctors can transfer]

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
JSON OUTPUT FORMAT - NODES AND EDGES TOGETHER
═══════════════════════════════════════════════════════════════════

CRITICAL: Elements array must contain BOTH nodes (classes) AND edges (relationships)

COMPLETE EXAMPLE FOR "ice cream shop database":

"""
        # Use raw string to avoid double brace escaping
        example_json = '''{
  "action": "create_class",
  "elements": [
    {
      "type": "node",
      "data": {
        "id": "class-TIMESTAMP-1",
        "data": {
          "label": "Customer",
          "nodeType": "class",
          "isAbstract": false,
          "attributes": [
            {"id": "attr-1-1", "name": "id", "type": "Long", "visibility": "private", "isStatic": false, "isFinal": false},
            {"id": "attr-1-2", "name": "nombre", "type": "String", "visibility": "private", "isStatic": false, "isFinal": false},
            {"id": "attr-1-3", "name": "email", "type": "String", "visibility": "private", "isStatic": false, "isFinal": false}
          ],
          "methods": []
        },
        "position": {"x": 100, "y": 100}
      }
    },
    {
      "type": "node",
      "data": {
        "id": "class-TIMESTAMP-2",
        "data": {
          "label": "Sale",
          "nodeType": "class",
          "isAbstract": false,
          "attributes": [
            {"id": "attr-2-1", "name": "id", "type": "Long", "visibility": "private", "isStatic": false, "isFinal": false},
            {"id": "attr-2-2", "name": "fecha", "type": "Date", "visibility": "private", "isStatic": false, "isFinal": false},
            {"id": "attr-2-3", "name": "total", "type": "Double", "visibility": "private", "isStatic": false, "isFinal": false}
          ],
          "methods": []
        },
        "position": {"x": 400, "y": 100}
      }
    },
    {
      "type": "node",
      "data": {
        "id": "class-TIMESTAMP-3",
        "data": {
          "label": "Product",
          "nodeType": "class",
          "isAbstract": false,
          "attributes": [
            {"id": "attr-3-1", "name": "id", "type": "Long", "visibility": "private", "isStatic": false, "isFinal": false},
            {"id": "attr-3-2", "name": "nombre", "type": "String", "visibility": "private", "isStatic": false, "isFinal": false},
            {"id": "attr-3-3", "name": "precio", "type": "Double", "visibility": "private", "isStatic": false, "isFinal": false}
          ],
          "methods": []
        },
        "position": {"x": 700, "y": 100}
      }
    },
    {
      "type": "edge",
      "data": {
        "id": "edge-TIMESTAMP-1",
        "source": "class-TIMESTAMP-1",
        "target": "class-TIMESTAMP-2",
        "type": "umlRelationship",
        "data": {
          "relationshipType": "ASSOCIATION",
          "sourceMultiplicity": "1",
          "targetMultiplicity": "*",
          "label": "places"
        }
      }
    },
    {
      "type": "edge",
      "data": {
        "id": "edge-TIMESTAMP-2",
        "source": "class-TIMESTAMP-2",
        "target": "class-TIMESTAMP-3",
        "type": "umlRelationship",
        "data": {
          "relationshipType": "COMPOSITION",
          "sourceMultiplicity": "1",
          "targetMultiplicity": "*",
          "label": "contains"
        }
      }
    }
  ],
  "confidence": 0.95,
  "interpretation": "Created ice cream shop database with 3 entities and 2 relationships using proper cardinality"
}'''
        base_prompt += example_json.replace('TIMESTAMP', str(timestamp_ms)) + "\n\n"
        
        base_prompt += """

KEY REQUIREMENTS:
1. Include BOTH node and edge objects in elements array
2. Node structure: type="node", data with id, data nested object, position
3. Edge structure: type="edge", data with id, source, target, type="umlRelationship", data with relationshipType
4. Use unique IDs with timestamp (replace TIMESTAMP with actual value)
5. Source and target in edges must match node IDs exactly

RELATIONSHIP TYPES (select appropriate):
- INHERITANCE: IS-A (Vehicle <- Car)
- COMPOSITION: Strong ownership (Order -> OrderItem)
- AGGREGATION: Weak containment (Department -> Employee)
- ASSOCIATION: General relationship (Customer -> Order)
- DEPENDENCY: Temporary usage (Service -> Logger)

MULTIPLICITY OPTIONS:
- "1" = exactly one
- "0..1" = optional (zero or one)
- "*" = zero or many
- "1..*" = one or many (required)

ATTRIBUTE TYPES:
- Long: id, codigo
- String: nombre, name, email, direccion
- Integer: edad, cantidad, stock
- Double: precio, monto, total
- Date: fecha, createdAt
- Boolean: activo, enabled

POSITIONING (avoid overlap):
- Row 1: x=100, 400, 700, 1000 at y=100
- Row 2: x=100, 400, 700, 1000 at y=400
- Row 3: x=100, 400, 700, 1000 at y=700

═══════════════════════════════════════════════════════════════════
PRE-GENERATION VALIDATION CHECKLIST
═══════════════════════════════════════════════════════════════════

Before generating JSON, systematically verify:

1. ENTITY VERIFICATION:
   [ ] Minimum 3-5 entities for database systems?
   [ ] Each entity has 3+ attributes including id (Long)?
   [ ] Entity names are singular nouns (Customer, not Customers)?
   [ ] All entities have clear business purpose?

2. RELATIONSHIP TYPE VERIFICATION:
   [ ] Each relationship has appropriate type (not all ASSOCIATION)?
   [ ] INHERITANCE used for IS-A relationships?
   [ ] COMPOSITION used for strong ownership?
   [ ] AGGREGATION used for weak containment?
   [ ] Relationship type distribution: ASSOCIATION 50-70%, others 30-50%?

3. CARDINALITY VERIFICATION:
   [ ] Applied systematic cardinality analysis for each relationship?
   [ ] Most relationships are 1:* (50-70%)?
   [ ] 1:1 relationships are rare (< 10%) and justified?
   [ ] Many-to-many includes junction table entity?
   [ ] Can explain each cardinality with business scenario?

4. STRUCTURAL VERIFICATION:
   [ ] Elements array contains BOTH nodes AND edges?
   [ ] At least N-1 edges for N nodes (minimum connectivity)?
   [ ] No orphaned classes (all connected)?
   [ ] Source/target IDs in edges match node IDs exactly?
   [ ] All IDs are unique with timestamp?

5. OUTPUT FORMAT VERIFICATION:
   [ ] Response starts with {{ (no text before)?
   [ ] Response ends with }} (no text after)?
   [ ] No explanatory text outside JSON?
   [ ] No markdown code blocks?
   [ ] Valid JSON syntax (no trailing commas)?

6. BUSINESS LOGIC VERIFICATION:
   [ ] Design matches real-world business operations?
   [ ] Relationships don't violate business rules?
   [ ] Schema supports typical CRUD operations?
   [ ] Design is production-ready, not toy example?
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
        base_prompt += "YOUR TASK - PROCESS THIS COMMAND\n"
        base_prompt += f"{'═'*70}\n\n"
        base_prompt += f'Command: "{command}"\n\n'
        
        base_prompt += "EXECUTION INSTRUCTIONS:\n\n"
        
        base_prompt += "1. Apply 6-Phase Reasoning Protocol (defined above)\n"
        base_prompt += "2. Use domain knowledge patterns for context\n"
        base_prompt += "3. Select appropriate relationship types (not just ASSOCIATION)\n"
        base_prompt += "4. Determine realistic cardinality (NOT all 1:1)\n"
        base_prompt += "5. Generate BOTH nodes AND edges in elements array\n"
        base_prompt += "6. Validate against checklist before output\n\n"
        
        base_prompt += "CRITICAL OUTPUT RULES:\n\n"
        
        base_prompt += "YOUR RESPONSE MUST START WITH {{ AND END WITH }}\n\n"
        
        base_prompt += "Example of CORRECT start:\n"
        base_prompt += "{{\n"
        base_prompt += '  "action": "create_class",\n'
        base_prompt += '  "elements": [...]\n'
        base_prompt += "}}\n\n"
        
        base_prompt += "Example of WRONG start (missing opening brace):\n"
        base_prompt += '  "action": "create_class",    ← WRONG, missing {{\n'
        base_prompt += '  "elements": [...]\n\n'
        
        base_prompt += "MANDATORY REQUIREMENTS:\n"
        base_prompt += "- First character MUST be {{ (opening brace)\n"
        base_prompt += "- Last character MUST be }} (closing brace)\n"
        base_prompt += "- NO whitespace before opening brace\n"
        base_prompt += "- NO whitespace after closing brace\n"
        base_prompt += "- NO text before {{\n"
        base_prompt += "- NO text after }}\n"
        base_prompt += "- NO markdown code blocks\n"
        base_prompt += "- NO explanatory comments\n"
        base_prompt += "- ONLY valid JSON object\n\n"
        
        base_prompt += "MINIMUM REQUIREMENTS:\n"
        base_prompt += f"- Timestamp for IDs: {timestamp_ms}\n"
        base_prompt += "- Entity count: 3-5 minimum for database systems\n"
        base_prompt += "- Attributes per entity: 3+ including id (Long)\n"
        base_prompt += "- Relationship count: At least N-1 edges for N nodes\n"
        base_prompt += "- Relationship types: Mix of ASSOCIATION, COMPOSITION, AGGREGATION\n"
        base_prompt += "- Cardinality: 50-70% one-to-many, <10% one-to-one\n\n"
        
        base_prompt += "NOW EXECUTE:\n"
        base_prompt += "Apply expert reasoning, generate complete UML class diagram with proper\n"
        base_prompt += "relationships and cardinality.\n\n"
        
        base_prompt += "BEFORE RETURNING YOUR RESPONSE - SELF-CHECK:\n\n"
        base_prompt += "1. Does response contain {{ anywhere? If YES: WRONG, use single { only\n"
        base_prompt += "2. Does response contain }} anywhere? If YES: WRONG, use single } only\n"
        base_prompt += "3. Does response contain <|eot_id|> or <| tags? If YES: WRONG, remove completely\n"
        base_prompt += "4. Does response have text before first {? If YES: WRONG, remove it\n"
        base_prompt += "5. Does response have text after final }? If YES: WRONG, remove it\n"
        base_prompt += "6. Does elements array have both nodes AND edges? If NO: WRONG, add edges\n"
        base_prompt += "7. Can I parse this as valid JSON? If NO: WRONG, fix syntax errors\n\n"
        
        base_prompt += "Only after ALL checks pass, return response.\n"
        base_prompt += "Invalid JSON triggers fallback to Nova Pro and wastes compute.\n\n"
        
        base_prompt += "Begin JSON response immediately:\n"
        
        return base_prompt
    
    def _format_llama_prompt(self, base_prompt: str) -> str:
        """
        Format prompt in Llama 4 Maverick specific format with JSON priming.
        
        Llama 4 requires special tokens for proper processing:
        - <|begin_of_text|> at start
        - <|start_header_id|>user<|end_header_id|> for user role
        - <|eot_id|> for end of turn
        - <|start_header_id|>assistant<|end_header_id|> for assistant role
        - Prime with single { to start JSON generation immediately
        
        Args:
            base_prompt: The base prompt content
            
        Returns:
            Formatted prompt with Llama 4 tokens
        """
        formatted = "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n"
        formatted += base_prompt
        # CRITICAL: Use SINGLE brace to prime JSON, not double brace
        # Put opening brace immediately after assistant header to force proper JSON start
        formatted += "\n<|eot_id|>\n<|start_header_id|>assistant<|end_header_id|>\n\n{"
        
        return formatted
    
    def _preprocess_response(self, response_text: str) -> str:
        """
        Preprocess response to remove Llama 4 format tags and fix missing braces.
        
        Args:
            response_text: Raw response from Llama 4
            
        Returns:
            Cleaned response text with valid JSON structure
        """
        original_length = len(response_text)
        
        # Remove Llama 4 format tags that may leak into output
        cleaned = response_text.replace('<|eot_id|>', '')
        cleaned = cleaned.replace('<|begin_of_text|>', '')
        cleaned = cleaned.replace('<|start_header_id|>assistant<|end_header_id|>', '')
        cleaned = cleaned.replace('<|start_header_id|>user<|end_header_id|>', '')
        cleaned = cleaned.replace('<|end_header_id|>', '')
        
        # Strip whitespace
        cleaned = cleaned.strip()
        
        logger.info(f"[PREPROCESSING] Removed {original_length - len(cleaned)} chars of format tags")
        logger.info(f"[PREPROCESSING] First 100 chars after cleanup: {cleaned[:100]}")
        
        # CRITICAL FIX: Add missing opening brace
        if not cleaned.startswith('{'):
            logger.warning("[PREPROCESSING] Response missing opening brace, adding it")
            logger.warning(f"[PREPROCESSING] Original start: {cleaned[:50]}")
            cleaned = '{' + cleaned
        
        # CRITICAL FIX: Add missing closing brace
        if not cleaned.endswith('}'):
            logger.warning("[PREPROCESSING] Response missing closing brace, adding it")
            logger.warning(f"[PREPROCESSING] Original end: {cleaned[-50:]}")
            cleaned = cleaned + '}'
        
        logger.info(f"[PREPROCESSING] Final length: {len(cleaned)} chars")
        
        return cleaned
    
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
        
        # CRITICAL: Preprocess to remove format tags
        response_text = self._preprocess_response(response_text)
        logger.info(f"[PARSING] After preprocessing: {len(response_text)} chars")
        logger.info(f"[PARSING] Cleaned preview (first 300 chars): {response_text[:300]}")
        
        strategies = [
            self._try_complete_json_extraction,  # NEW: Comprehensive extraction
            self._try_direct_parse,
            self._try_brace_counting,
            self._try_markdown_extraction,
            self._try_json_block_extraction,
            self._try_last_valid_json  # LAST RESORT
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
                    
                    # CRITICAL VALIDATION: Check if we got a nested object instead of root
                    if 'action' not in result:
                        logger.error("[PARSING] Result missing 'action' field - likely extracted nested object")
                        if 'type' in result:
                            logger.error(f"[PARSING] Found 'type' field with value '{result.get('type')}' - this is a nested node/edge, not root")
                        logger.error(f"[PARSING] All keys: {list(result.keys())}")
                        continue  # Try next strategy
                    
                    if 'elements' not in result:
                        logger.error("[PARSING] Result missing 'elements' field")
                        logger.error(f"[PARSING] All keys: {list(result.keys())}")
                        continue  # Try next strategy
                    
                    validated_result = self._validate_and_normalize_result(result)
                    logger.info(f"[PARSING] After validation - Action: {validated_result.get('action')}, Elements: {len(validated_result.get('elements', []))}")
                    return validated_result
                else:
                    logger.warning(f"[PARSING] Strategy {strategy.__name__} returned None")
            except Exception as e:
                logger.warning(f"[PARSING] Strategy {strategy.__name__} failed with error: {e}")
                continue
        
        logger.error(f"[PARSING] ALL {len(strategies)} STRATEGIES FAILED")
        logger.error(f"[PARSING] Full response text ({len(response_text)} chars):\n{response_text}")
        
        # Diagnose common failure patterns
        logger.error("[PARSING] DIAGNOSTIC ANALYSIS:")
        
        if '"action"' in response_text:
            logger.error("[PARSING] ✓ Found 'action' keyword in response")
            action_pos = response_text.find('"action"')
            logger.error(f"[PARSING]   Position: {action_pos}")
            logger.error(f"[PARSING]   Context: {response_text[max(0, action_pos-30):action_pos+50]}")
        else:
            logger.error("[PARSING] ✗ No 'action' keyword found - Llama 4 generated wrong format")
        
        if '"elements"' in response_text:
            logger.error("[PARSING] ✓ Found 'elements' keyword in response")
        else:
            logger.error("[PARSING] ✗ No 'elements' keyword found")
        
        if response_text.strip().startswith('{'):
            logger.error("[PARSING] ✓ Response starts with opening brace")
        else:
            logger.error("[PARSING] ✗ Response missing opening brace")
            logger.error(f"[PARSING]   First 50 chars: {response_text[:50]}")
        
        if response_text.strip().endswith('}'):
            logger.error("[PARSING] ✓ Response ends with closing brace")
        else:
            logger.error("[PARSING] ✗ Response missing closing brace")
            logger.error(f"[PARSING]   Last 50 chars: {response_text[-50:]}")
        
        # Count braces
        open_braces = response_text.count('{')
        close_braces = response_text.count('}')
        logger.error(f"[PARSING] Brace count: {{ = {open_braces}, }} = {close_braces}")
        
        if open_braces != close_braces:
            logger.error("[PARSING] ✗ Unbalanced braces - JSON structure invalid")
        
        return {
            'action': 'error',
            'elements': [],
            'confidence': 0.0,
            'interpretation': 'Could not parse Llama 4 Maverick response',
            'error': 'Failed to extract valid JSON from all strategies',
            'raw_response_preview': response_text[:500],
            'diagnostics': {
                'has_action': '"action"' in response_text,
                'has_elements': '"elements"' in response_text,
                'starts_with_brace': response_text.strip().startswith('{'),
                'ends_with_brace': response_text.strip().endswith('}'),
                'open_braces': open_braces,
                'close_braces': close_braces
            }
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
    
    def _try_complete_json_extraction(self, text: str) -> Optional[Dict]:
        """
        Comprehensive JSON extraction strategy with validation.
        
        Finds the "action" keyword and extracts complete JSON object
        using brace counting while respecting strings and escaping.
        
        This strategy avoids the problem of _try_last_valid_json which
        only returns the last object, losing array content.
        
        Args:
            text: Response text to parse
            
        Returns:
            Parsed JSON dict with action and elements, or None
        """
        logger.debug("[COMPLETE_EXTRACTION] Starting comprehensive extraction")
        
        # Find "action" keyword (indicates start of our JSON)
        action_index = text.find('"action"')
        if action_index == -1:
            logger.debug("[COMPLETE_EXTRACTION] No 'action' keyword found")
            return None
        
        # Search backwards from action to find opening brace
        # (look up to 100 chars before action to handle leading whitespace)
        start_index = -1
        search_start = max(0, action_index - 100)
        for i in range(action_index - 1, search_start - 1, -1):
            if text[i] == '{':
                start_index = i
                break
        
        if start_index == -1:
            logger.warning("[COMPLETE_EXTRACTION] No opening brace found before 'action'")
            logger.warning("[COMPLETE_EXTRACTION] This means Llama 4 didn't output opening brace")
            logger.warning(f"[COMPLETE_EXTRACTION] Text before action: {text[max(0, action_index-50):action_index]}")
            
            # Emergency fix: Assume text starts at beginning
            start_index = 0
            logger.warning("[COMPLETE_EXTRACTION] Using start of text as JSON start")
        
        logger.debug(f"[COMPLETE_EXTRACTION] Found opening brace at position {start_index}")
        
        # Use brace counting to find matching closing brace
        # Properly handle strings and escape sequences
        brace_count = 0
        in_string = False
        escape_next = False
        
        for i in range(start_index, len(text)):
            char = text[i]
            
            # Handle escape sequences
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            # Handle string boundaries
            if char == '"':
                in_string = not in_string
                continue
            
            # Only count braces outside of strings
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    
                    # Found matching closing brace
                    if brace_count == 0:
                        json_text = text[start_index:i+1]
                        logger.debug(f"[COMPLETE_EXTRACTION] Extracted {len(json_text)} chars of JSON")
                        logger.debug(f"[COMPLETE_EXTRACTION] JSON preview: {json_text[:200]}...")
                        
                        try:
                            parsed = json.loads(json_text)
                            
                            # CRITICAL VALIDATION: Check for required fields
                            if 'action' not in parsed:
                                logger.warning("[COMPLETE_EXTRACTION] Parsed JSON missing 'action' field")
                                logger.warning(f"[COMPLETE_EXTRACTION] Keys found: {list(parsed.keys())}")
                                return None
                            
                            if 'elements' not in parsed:
                                logger.warning("[COMPLETE_EXTRACTION] Parsed JSON missing 'elements' field")
                                logger.warning(f"[COMPLETE_EXTRACTION] Keys found: {list(parsed.keys())}")
                                return None
                            
                            if not isinstance(parsed['elements'], list):
                                logger.warning(f"[COMPLETE_EXTRACTION] 'elements' is not a list: {type(parsed['elements'])}")
                                return None
                            
                            logger.info(f"[COMPLETE_EXTRACTION] SUCCESS - validated JSON with action='{parsed['action']}' and {len(parsed['elements'])} elements")
                            return parsed
                            
                        except json.JSONDecodeError as e:
                            logger.warning(f"[COMPLETE_EXTRACTION] JSON parse error: {e}")
                            return None
        
        logger.debug("[COMPLETE_EXTRACTION] No matching closing brace found")
        return None
    
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
        """
        Extract JSON by finding balanced braces with validation.
        
        Tries multiple opening brace positions to find the root object
        that contains 'action' and 'elements' fields.
        """
        # Find all potential opening brace positions
        potential_starts = [i for i, char in enumerate(text) if char == '{']
        
        if not potential_starts:
            logger.debug("[BRACE_COUNTING] No opening braces found")
            return None
        
        logger.debug(f"[BRACE_COUNTING] Found {len(potential_starts)} potential opening braces")
        
        # Try each potential start position
        for start_idx, start_pos in enumerate(potential_starts):
            logger.debug(f"[BRACE_COUNTING] Trying brace position {start_idx + 1}/{len(potential_starts)} at char {start_pos}")
            
            brace_count = 0
            in_string = False
            escape = False
            
            for i in range(start_pos, len(text)):
                char = text[i]
                
                # Handle escape sequences
                if escape:
                    escape = False
                    continue
                
                if char == '\\':
                    escape = True
                    continue
                
                # Handle string boundaries
                if char == '"':
                    in_string = not in_string
                    continue
                
                # Only count braces outside strings
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        
                        # Found matching closing brace
                        if brace_count == 0:
                            json_str = text[start_pos:i+1]
                            logger.debug(f"[BRACE_COUNTING] Extracted {len(json_str)} chars from position {start_pos}")
                            
                            try:
                                parsed = json.loads(json_str)
                                
                                # Validate this is the root object we want
                                if 'action' in parsed and 'elements' in parsed:
                                    logger.info(f"[BRACE_COUNTING] SUCCESS - found root object with action and {len(parsed['elements'])} elements")
                                    return parsed
                                else:
                                    logger.debug(f"[BRACE_COUNTING] Valid JSON but missing required fields (keys: {list(parsed.keys())})")
                                    # Continue to try next brace position
                                    break
                                    
                            except json.JSONDecodeError as e:
                                logger.debug(f"[BRACE_COUNTING] JSON parse error at position {start_pos}: {e}")
                                # Continue to try next brace position
                                break
            
            # If we get here, this start position didn't work, try next
        
        logger.debug("[BRACE_COUNTING] All brace positions exhausted without finding valid root object")
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
