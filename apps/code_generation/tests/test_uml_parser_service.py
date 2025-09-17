"""
Tests for UMLParserService - SpringBoot code generation UML parsing.
"""

import unittest
from unittest.mock import Mock, patch
from django.test import TestCase

from ..services.uml_parser_service import UMLParserService


class UMLParserServiceTestCase(TestCase):
    """Test cases for UMLParserService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = UMLParserService()
        self.sample_uml_data = {
            "classes": [
                {
                    "id": "class1",
                    "name": "User",
                    "attributes": [
                        {"name": "id", "type": "Long", "visibility": "private"},
                        {"name": "username", "type": "String", "visibility": "private"},
                        {"name": "email", "type": "String", "visibility": "private"}
                    ],
                    "methods": [
                        {"name": "getId", "returnType": "Long", "visibility": "public"},
                        {"name": "setId", "parameters": [{"name": "id", "type": "Long"}], "visibility": "public"}
                    ],
                    "stereotypes": ["Entity"]
                }
            ],
            "relationships": [
                {
                    "id": "rel1",
                    "type": "OneToMany",
                    "source": "class1",
                    "target": "class2",
                    "sourceMultiplicity": "1",
                    "targetMultiplicity": "*"
                }
            ]
        }
    
    def test_parse_uml_diagram_success(self):
        """Test successful UML diagram parsing."""
        result = self.parser.parse_uml_diagram(self.sample_uml_data)
        
        self.assertIsInstance(result, dict)
        self.assertIn('classes', result)
        self.assertIn('relationships', result)
        self.assertEqual(len(result['classes']), 1)
        self.assertEqual(len(result['relationships']), 1)
    
    def test_parse_uml_diagram_empty_data(self):
        """Test parsing with empty UML data."""
        empty_data = {"classes": [], "relationships": []}
        result = self.parser.parse_uml_diagram(empty_data)
        
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result['classes']), 0)
        self.assertEqual(len(result['relationships']), 0)
    
    def test_parse_uml_diagram_invalid_data(self):
        """Test parsing with invalid UML data."""
        invalid_data = {"invalid": "data"}
        
        with self.assertRaises(ValueError):
            self.parser.parse_uml_diagram(invalid_data)
    
    def test_extract_class_info(self):
        """Test class information extraction."""
        class_data = self.sample_uml_data["classes"][0]
        result = self.parser.extract_class_info(class_data)
        
        self.assertEqual(result['name'], 'User')
        self.assertEqual(result['package'], 'com.example.entity')
        self.assertIn('attributes', result)
        self.assertIn('methods', result)
        self.assertIn('annotations', result)
    
    def test_extract_class_attributes(self):
        """Test class attribute extraction."""
        class_data = self.sample_uml_data["classes"][0]
        attributes = self.parser.extract_class_attributes(class_data['attributes'])
        
        self.assertEqual(len(attributes), 3)
        
        id_attr = attributes[0]
        self.assertEqual(id_attr['name'], 'id')
        self.assertEqual(id_attr['java_type'], 'Long')
        self.assertIn('@Id', id_attr['annotations'])
        self.assertIn('@GeneratedValue', id_attr['annotations'])
    
    def test_extract_class_methods(self):
        """Test class method extraction."""
        class_data = self.sample_uml_data["classes"][0]
        methods = self.parser.extract_class_methods(class_data['methods'])
        
        self.assertEqual(len(methods), 2)
        
        getter = methods[0]
        self.assertEqual(getter['name'], 'getId')
        self.assertEqual(getter['return_type'], 'Long')
        self.assertEqual(getter['visibility'], 'public')
    
    def test_extract_relationships(self):
        """Test relationship extraction."""
        relationships = self.parser.extract_relationships(self.sample_uml_data['relationships'])
        
        self.assertEqual(len(relationships), 1)
        
        relationship = relationships[0]
        self.assertEqual(relationship['type'], 'OneToMany')
        self.assertIn('source_annotations', relationship)
        self.assertIn('target_annotations', relationship)
    
    def test_map_uml_type_to_java(self):
        """Test UML type to Java type mapping."""
        type_mappings = [
            ('String', 'String'),
            ('Integer', 'Integer'),
            ('Long', 'Long'),
            ('Boolean', 'Boolean'),
            ('Date', 'LocalDateTime'),
            ('Decimal', 'BigDecimal'),
            ('Text', 'String'),
            ('Unknown', 'Object')
        ]
        
        for uml_type, expected_java_type in type_mappings:
            with self.subTest(uml_type=uml_type):
                result = self.parser.map_uml_type_to_java(uml_type)
                self.assertEqual(result, expected_java_type)
    
    def test_generate_jpa_annotations(self):
        """Test JPA annotation generation."""
        attribute = {
            'name': 'id',
            'type': 'Long',
            'is_primary_key': True,
            'is_nullable': False
        }
        
        annotations = self.parser.generate_jpa_annotations(attribute)
        
        self.assertIn('@Id', annotations)
        self.assertIn('@GeneratedValue', annotations)
        self.assertIn('@Column', annotations)
    
    def test_generate_validation_annotations(self):
        """Test validation annotation generation."""
        attribute = {
            'name': 'email',
            'type': 'String',
            'is_nullable': False,
            'constraints': {
                'email': True,
                'max_length': 255
            }
        }
        
        annotations = self.parser.generate_validation_annotations(attribute)
        
        self.assertIn('@NotNull', annotations)
        self.assertIn('@Email', annotations)
        self.assertIn('@Size(max = 255)', annotations)
    
    def test_generate_relationship_annotations(self):
        """Test relationship annotation generation."""
        relationship = {
            'type': 'OneToMany',
            'target_class': 'Order',
            'mapped_by': 'user',
            'cascade': ['PERSIST', 'MERGE'],
            'fetch_type': 'LAZY'
        }
        
        annotations = self.parser.generate_relationship_annotations(relationship)
        
        self.assertIn('@OneToMany', annotations)
        self.assertIn('mappedBy = "user"', annotations[0])
        self.assertIn('cascade', annotations[0])
        self.assertIn('fetch = FetchType.LAZY', annotations[0])
    
    def test_extract_imports(self):
        """Test import statement extraction."""
        class_info = {
            'attributes': [
                {'java_type': 'String', 'annotations': ['@NotNull']},
                {'java_type': 'LocalDateTime', 'annotations': ['@Column']}
            ],
            'relationships': [
                {'type': 'OneToMany', 'target_class': 'Order'}
            ]
        }
        
        imports = self.parser.extract_imports(class_info)
        
        expected_imports = [
            'javax.persistence.*',
            'javax.validation.constraints.*',
            'java.time.LocalDateTime',
            'java.util.List'
        ]
        
        for expected_import in expected_imports:
            self.assertIn(expected_import, imports)
    
    def test_generate_springboot_metadata(self):
        """Test SpringBoot metadata generation."""
        parsed_data = self.parser.parse_uml_diagram(self.sample_uml_data)
        metadata = self.parser.generate_springboot_metadata(parsed_data)
        
        self.assertIn('entities', metadata)
        self.assertIn('repositories', metadata)
        self.assertIn('services', metadata)
        self.assertIn('controllers', metadata)
        
        # Check entity metadata
        entities = metadata['entities']
        self.assertEqual(len(entities), 1)
        
        user_entity = entities[0]
        self.assertEqual(user_entity['class_name'], 'User')
        self.assertEqual(user_entity['table_name'], 'users')
        self.assertIn('package', user_entity)
    
    def test_error_handling_malformed_data(self):
        """Test error handling with malformed data."""
        malformed_data = {
            "classes": [
                {
                    "name": None,  # Invalid name
                    "attributes": "not_a_list"  # Invalid attributes
                }
            ]
        }
        
        with self.assertRaises(ValueError) as context:
            self.parser.parse_uml_diagram(malformed_data)
        
        self.assertIn("Invalid class data", str(context.exception))
    
    def test_parse_complex_relationships(self):
        """Test parsing complex relationship scenarios."""
        complex_relationships = [
            {
                "type": "ManyToMany",
                "source": "User",
                "target": "Role",
                "join_table": "user_roles",
                "join_columns": [
                    {"name": "user_id", "referenced_column": "id"},
                    {"name": "role_id", "referenced_column": "id"}
                ]
            }
        ]
        
        relationships = self.parser.extract_relationships(complex_relationships)
        
        self.assertEqual(len(relationships), 1)
        relationship = relationships[0]
        
        self.assertEqual(relationship['type'], 'ManyToMany')
        self.assertIn('@JoinTable', relationship['source_annotations'])
        self.assertIn('user_roles', relationship['source_annotations'][0])
    
    def test_generate_dto_metadata(self):
        """Test DTO metadata generation."""
        class_info = {
            'name': 'User',
            'attributes': [
                {'name': 'id', 'type': 'Long'},
                {'name': 'username', 'type': 'String'},
                {'name': 'password', 'type': 'String', 'exclude_from_dto': True}
            ]
        }
        
        dto_metadata = self.parser.generate_dto_metadata(class_info)
        
        self.assertEqual(dto_metadata['class_name'], 'UserDto')
        self.assertEqual(len(dto_metadata['fields']), 2)  # password excluded
        
        field_names = [field['name'] for field in dto_metadata['fields']]
        self.assertIn('id', field_names)
        self.assertIn('username', field_names)
        self.assertNotIn('password', field_names)


class UMLParserServiceIntegrationTestCase(TestCase):
    """Integration tests for UMLParserService with complex scenarios."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.parser = UMLParserService()
        self.complex_uml_data = {
            "classes": [
                {
                    "id": "user",
                    "name": "User",
                    "attributes": [
                        {"name": "id", "type": "Long", "visibility": "private"},
                        {"name": "username", "type": "String", "visibility": "private", "constraints": {"unique": True}},
                        {"name": "email", "type": "String", "visibility": "private", "constraints": {"email": True}},
                        {"name": "createdAt", "type": "Date", "visibility": "private"},
                        {"name": "isActive", "type": "Boolean", "visibility": "private", "default": True}
                    ],
                    "stereotypes": ["Entity", "Auditable"]
                },
                {
                    "id": "order",
                    "name": "Order",
                    "attributes": [
                        {"name": "id", "type": "Long", "visibility": "private"},
                        {"name": "orderNumber", "type": "String", "visibility": "private"},
                        {"name": "total", "type": "Decimal", "visibility": "private"},
                        {"name": "status", "type": "OrderStatus", "visibility": "private"}
                    ],
                    "stereotypes": ["Entity"]
                }
            ],
            "relationships": [
                {
                    "type": "OneToMany",
                    "source": "user",
                    "target": "order",
                    "sourceRole": "user",
                    "targetRole": "orders",
                    "cascade": ["PERSIST", "MERGE"]
                }
            ]
        }
    
    def test_full_parsing_workflow(self):
        """Test complete parsing workflow with complex UML data."""
        result = self.parser.parse_uml_diagram(self.complex_uml_data)
        
        # Verify structure
        self.assertIn('classes', result)
        self.assertIn('relationships', result)
        
        # Verify classes
        classes = result['classes']
        self.assertEqual(len(classes), 2)
        
        user_class = next((c for c in classes if c['name'] == 'User'), None)
        self.assertIsNotNone(user_class)
        self.assertEqual(user_class['table_name'], 'users')
        self.assertIn('@Entity', user_class['annotations'])
        
        # Verify attributes with constraints
        username_attr = next((attr for attr in user_class['attributes'] if attr['name'] == 'username'), None)
        self.assertIsNotNone(username_attr)
        self.assertIn('@Column(unique = true)', username_attr['annotations'])
        
        email_attr = next((attr for attr in user_class['attributes'] if attr['name'] == 'email'), None)
        self.assertIsNotNone(email_attr)
        self.assertIn('@Email', email_attr['annotations'])
        
        # Verify relationships
        relationships = result['relationships']
        self.assertEqual(len(relationships), 1)
        
        user_orders_rel = relationships[0]
        self.assertEqual(user_orders_rel['type'], 'OneToMany')
        self.assertIn('cascade = {CascadeType.PERSIST, CascadeType.MERGE}', user_orders_rel['source_annotations'][0])
    
    def test_springboot_metadata_generation(self):
        """Test SpringBoot metadata generation for complex scenario."""
        parsed_data = self.parser.parse_uml_diagram(self.complex_uml_data)
        metadata = self.parser.generate_springboot_metadata(parsed_data)
        
        # Verify entities
        entities = metadata['entities']
        self.assertEqual(len(entities), 2)
        
        user_entity = next((e for e in entities if e['class_name'] == 'User'), None)
        self.assertIsNotNone(user_entity)
        self.assertEqual(user_entity['package'], 'com.example.entity')
        self.assertIn('imports', user_entity)
        
        # Verify repositories
        repositories = metadata['repositories']
        self.assertEqual(len(repositories), 2)
        
        user_repo = next((r for r in repositories if r['entity_name'] == 'User'), None)
        self.assertIsNotNone(user_repo)
        self.assertEqual(user_repo['class_name'], 'UserRepository')
        
        # Verify services
        services = metadata['services']
        self.assertEqual(len(services), 2)
        
        user_service = next((s for s in services if s['entity_name'] == 'User'), None)
        self.assertIsNotNone(user_service)
        self.assertEqual(user_service['class_name'], 'UserService')
        
        # Verify controllers
        controllers = metadata['controllers']
        self.assertEqual(len(controllers), 2)
        
        user_controller = next((c for c in controllers if c['entity_name'] == 'User'), None)
        self.assertIsNotNone(user_controller)
        self.assertEqual(user_controller['class_name'], 'UserController')
        self.assertEqual(user_controller['base_path'], '/api/users')


if __name__ == '__main__':
    unittest.main()
