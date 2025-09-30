"""
UML Parser Service for analyzing and mapping UML diagrams to SpringBoot structures.
"""

from typing import Dict, List, Tuple, Optional
import re


class UMLParserService:
    """
    Service for parsing UML diagrams and extracting SpringBoot-relevant information.
    """
    
    def __init__(self):
        self.java_type_mapping = {
            'String': 'String',
            'Integer': 'Integer',
            'Long': 'Long',
            'Double': 'Double',
            'Float': 'Float',
            'Boolean': 'Boolean',
            'Date': 'LocalDateTime',
            'LocalDate': 'LocalDate',
            'LocalTime': 'LocalTime',
            'BigDecimal': 'BigDecimal',
            'UUID': 'UUID',
            'List': 'List',
            'Set': 'Set',
            'Map': 'Map'
        }
    
    def parse_diagram_structure(self, diagram) -> Dict:
        """
        Parse complete UML diagram structure.
        
        Returns:
            Structured data optimized for SpringBoot code generation
        """
        diagram_data = diagram.diagram_data
        
        parsed_structure = {
            'diagram_info': {
                'id': str(diagram.id),
                'name': diagram.name,
                'type': diagram.diagram_type,
                'description': diagram.description
            },
            'classes': self._parse_classes(diagram_data.get('classes', [])),
            'relationships': self._parse_relationships(diagram_data.get('relationships', [])),
            'packages': self._extract_packages(diagram_data.get('classes', [])),
            'springboot_metadata': self._generate_springboot_metadata(diagram_data)
        }

        parsed_structure['relationship_mappings'] = self._create_relationship_mappings(
            parsed_structure['classes'], parsed_structure['relationships']
        )
        
        return parsed_structure
    
    def _parse_classes(self, classes_data: List[Dict]) -> List[Dict]:
        """Parse UML classes for SpringBoot generation."""
        parsed_classes = []
        
        for class_data in classes_data:
            parsed_class = {
                'id': class_data.get('id'),
                'name': class_data.get('name'),
                'package': class_data.get('package', ''),
                'class_type': class_data.get('class_type', 'CLASS'),
                'visibility': class_data.get('visibility', 'PUBLIC'),
                'is_abstract': class_data.get('is_abstract', False),
                'stereotype': class_data.get('stereotype', ''),
                'documentation': class_data.get('documentation', ''),
                'attributes': self._parse_attributes(class_data.get('attributes', [])),
                'methods': self._parse_methods(class_data.get('methods', [])),
                'position': {
                    'x': class_data.get('position_x', 0),
                    'y': class_data.get('position_y', 0)
                },
                'springboot_mapping': self._generate_class_springboot_mapping(class_data)
            }
            
            parsed_classes.append(parsed_class)
        
        return parsed_classes
    
    def _parse_attributes(self, attributes_data: List[Dict]) -> List[Dict]:
        """Parse class attributes with SpringBoot type mapping."""
        parsed_attributes = []
        
        for attr_data in attributes_data:
            parsed_attr = {
                'id': attr_data.get('id'),
                'name': attr_data.get('name'),
                'type': attr_data.get('type'),
                'java_type': self.map_uml_type_to_java(attr_data.get('type', '')),
                'visibility': attr_data.get('visibility', 'PRIVATE'),
                'is_static': attr_data.get('is_static', False),
                'is_final': attr_data.get('is_final', False),
                'default_value': attr_data.get('default_value'),
                'documentation': attr_data.get('documentation', ''),
                'annotations': self._generate_attribute_annotations(attr_data),
                'validation_rules': self._extract_validation_rules(attr_data),
                'jpa_mapping': self._generate_jpa_attribute_mapping(attr_data)
            }
            
            parsed_attributes.append(parsed_attr)
        
        return parsed_attributes
    
    def _parse_methods(self, methods_data: List[Dict]) -> List[Dict]:
        """Parse class methods for SpringBoot generation."""
        parsed_methods = []
        
        for method_data in methods_data:
            parsed_method = {
                'id': method_data.get('id'),
                'name': method_data.get('name'),
                'return_type': method_data.get('return_type', 'void'),
                'java_return_type': self.map_uml_type_to_java(method_data.get('return_type', 'void')),
                'visibility': method_data.get('visibility', 'PUBLIC'),
                'is_static': method_data.get('is_static', False),
                'is_abstract': method_data.get('is_abstract', False),
                'is_final': method_data.get('is_final', False),
                'parameters': self._parse_method_parameters(method_data.get('parameters', [])),
                'documentation': method_data.get('documentation', ''),
                'annotations': method_data.get('annotations', []),
                'exceptions': method_data.get('exceptions', []),
                'springboot_mapping': self._generate_method_springboot_mapping(method_data)
            }
            
            parsed_methods.append(parsed_method)
        
        return parsed_methods
    
    def _parse_method_parameters(self, parameters_data: List[Dict]) -> List[Dict]:
        """Parse method parameters with type mapping."""
        parsed_params = []
        
        for param_data in parameters_data:
            parsed_param = {
                'name': param_data.get('name'),
                'type': param_data.get('type'),
                'java_type': self.map_uml_type_to_java(param_data.get('type', '')),
                'is_final': param_data.get('is_final', False),
                'default_value': param_data.get('default_value'),
                'annotations': param_data.get('annotations', [])
            }
            
            parsed_params.append(parsed_param)
        
        return parsed_params
    
    def _parse_relationships(self, relationships_data: List[Dict]) -> List[Dict]:
        """Parse UML relationships for JPA mapping."""
        parsed_relationships = []
        
        for rel_data in relationships_data:
            parsed_rel = {
                'id': rel_data.get('id'),
                'name': rel_data.get('name', ''),
                'type': rel_data.get('relationship_type'),
                'source_id': rel_data.get('source_id'),
                'target_id': rel_data.get('target_id'),
                'source_multiplicity': rel_data.get('source_multiplicity', '1'),
                'target_multiplicity': rel_data.get('target_multiplicity', '1'),
                'source_role': rel_data.get('source_role', ''),
                'target_role': rel_data.get('target_role', ''),
                'source_navigable': rel_data.get('source_navigable', True),
                'target_navigable': rel_data.get('target_navigable', True),
                'jpa_mapping': self._generate_relationship_jpa_mapping(rel_data)
            }
            
            parsed_relationships.append(parsed_rel)
        
        return parsed_relationships
    
    def _extract_packages(self, classes_data: List[Dict]) -> List[str]:
        """Extract unique packages from classes."""
        packages = set()
        
        for class_data in classes_data:
            package = class_data.get('package', '')
            if package:
                packages.add(package)
        
        return sorted(list(packages))
    
    def _generate_springboot_metadata(self, diagram_data: Dict) -> Dict:
        """Generate SpringBoot-specific metadata from diagram."""
        classes_count = len(diagram_data.get('classes', []))
        relationships_count = len(diagram_data.get('relationships', []))
        
        return {
            'entities_count': classes_count,
            'relationships_count': relationships_count,
            'complexity_score': (classes_count * 2) + relationships_count,
            'requires_jpa': relationships_count > 0,
            'requires_validation': self._has_validation_requirements(diagram_data),
            'requires_security': self._has_security_requirements(diagram_data),
            'suggested_dependencies': self._suggest_springboot_dependencies(diagram_data)
        }
    
    def _generate_class_springboot_mapping(self, class_data: Dict) -> Dict:
        """Generate SpringBoot mapping for UML class."""
        class_name = class_data.get('name', '')
        
        return {
            'entity_name': class_name,
            'table_name': self._to_snake_case(class_name),
            'repository_name': f"{class_name}Repository",
            'service_name': f"{class_name}Service",
            'controller_name': f"{class_name}Controller",
            'dto_name': f"{class_name}DTO",
            'api_path': self._to_kebab_case(class_name).lower(),
            'is_entity': class_data.get('stereotype', '').lower() in ['entity', 'model', ''] or 
                        'entity' in class_name.lower(),
            'requires_crud': True
        }
    
    def _generate_attribute_annotations(self, attr_data: Dict) -> List[str]:
        """Generate JPA and validation annotations for attribute."""
        annotations = []
        attr_name = attr_data.get('name', '').lower()
        attr_type = attr_data.get('type', '')

        if attr_name == 'id':
            annotations.extend(['@Id', '@GeneratedValue(strategy = GenerationType.IDENTITY)'])
        
        if attr_data.get('is_final'):
            annotations.append('@Column(nullable = false)')

        if 'string' in attr_type.lower() and attr_name not in ['id']:
            annotations.append('@NotBlank')
        elif attr_type.lower() in ['integer', 'long', 'double', 'float'] and attr_name not in ['id']:
            annotations.append('@NotNull')

        if attr_name in ['created_at', 'createdat', 'created_date']:
            annotations.append('@CreationTimestamp')
        elif attr_name in ['updated_at', 'updatedat', 'modified_date', 'last_modified']:
            annotations.append('@UpdateTimestamp')
        
        return annotations
    
    def _generate_jpa_attribute_mapping(self, attr_data: Dict) -> Dict:
        """Generate JPA mapping configuration for attribute."""
        attr_name = attr_data.get('name', '')
        attr_type = attr_data.get('type', '')
        
        mapping = {
            'column_name': self._to_snake_case(attr_name),
            'is_primary_key': attr_name.lower() == 'id',
            'is_nullable': not attr_data.get('is_final', False),
            'is_unique': attr_name.lower() in ['email', 'username', 'code'],
            'length': self._determine_column_length(attr_type),
            'precision': self._determine_precision(attr_type),
            'scale': self._determine_scale(attr_type)
        }
        
        return mapping
    
    def _generate_relationship_jpa_mapping(self, rel_data: Dict) -> Dict:
        """Generate JPA relationship mapping."""
        rel_type = rel_data.get('relationship_type', '')
        source_multiplicity = rel_data.get('source_multiplicity', '1')
        target_multiplicity = rel_data.get('target_multiplicity', '1')

        if self._is_one_to_one(source_multiplicity, target_multiplicity):
            jpa_type = 'OneToOne'
        elif self._is_one_to_many(source_multiplicity, target_multiplicity):
            jpa_type = 'OneToMany'
        elif self._is_many_to_one(source_multiplicity, target_multiplicity):
            jpa_type = 'ManyToOne'
        elif self._is_many_to_many(source_multiplicity, target_multiplicity):
            jpa_type = 'ManyToMany'
        else:
            jpa_type = 'ManyToOne'  # Default
        
        mapping = {
            'jpa_annotation': jpa_type,
            'fetch_type': 'LAZY' if 'many' in jpa_type.lower() else 'EAGER',
            'cascade_types': self._determine_cascade_types(rel_type),
            'join_column': self._generate_join_column_name(rel_data),
            'mapped_by': self._generate_mapped_by(rel_data) if rel_data.get('target_navigable') else None
        }
        
        return mapping
    
    def _create_relationship_mappings(self, classes: List[Dict], 
                                    relationships: List[Dict]) -> Dict:
        """Create comprehensive relationship mappings for code generation."""
        class_map = {cls['id']: cls for cls in classes}
        mappings = {}
        
        for rel in relationships:
            source_class = class_map.get(rel['source_id'])
            target_class = class_map.get(rel['target_id'])
            
            if source_class and target_class:
                mapping_key = f"{source_class['name']}_to_{target_class['name']}"
                
                mappings[mapping_key] = {
                    'source_class': source_class['name'],
                    'target_class': target_class['name'],
                    'relationship_type': rel['type'],
                    'jpa_mapping': rel['jpa_mapping'],
                    'field_name_source': self._generate_field_name(target_class['name'], rel['target_multiplicity']),
                    'field_name_target': self._generate_field_name(source_class['name'], rel['source_multiplicity']) if rel['target_navigable'] else None
                }
        
        return mappings
    
    def map_uml_type_to_java(self, uml_type: str) -> str:
        """Map UML data type to Java type."""
        return self.java_type_mapping.get(uml_type, uml_type)
    
    def _extract_validation_rules(self, attr_data: Dict) -> List[Dict]:
        """Extract validation rules from attribute documentation or annotations."""
        rules = []
        documentation = attr_data.get('documentation', '').lower()
        
        if 'required' in documentation or attr_data.get('is_final'):
            rules.append({'type': 'NotNull', 'message': 'Field is required'})
        
        if 'email' in attr_data.get('name', '').lower():
            rules.append({'type': 'Email', 'message': 'Must be valid email'})

        length_match = re.search(r'length\s*:\s*(\d+)', documentation)
        if length_match:
            max_length = int(length_match.group(1))
            rules.append({'type': 'Size', 'max': max_length})
        
        return rules
    
    def _has_validation_requirements(self, diagram_data: Dict) -> bool:
        """Check if diagram requires validation dependencies."""
        for class_data in diagram_data.get('classes', []):
            for attr in class_data.get('attributes', []):
                if attr.get('is_final') or 'required' in attr.get('documentation', '').lower():
                    return True
        return False
    
    def _has_security_requirements(self, diagram_data: Dict) -> bool:
        """Check if diagram has security-related classes."""
        security_keywords = ['user', 'auth', 'security', 'login', 'password', 'token']
        
        for class_data in diagram_data.get('classes', []):
            class_name = class_data.get('name', '').lower()
            if any(keyword in class_name for keyword in security_keywords):
                return True
        
        return False
    
    def _suggest_springboot_dependencies(self, diagram_data: Dict) -> List[str]:
        """Suggest SpringBoot dependencies based on diagram content."""
        dependencies = [
            'spring-boot-starter-web',
            'spring-boot-starter-data-jpa',
            'spring-boot-starter-test'
        ]
        
        if self._has_validation_requirements(diagram_data):
            dependencies.append('spring-boot-starter-validation')
        
        if self._has_security_requirements(diagram_data):
            dependencies.append('spring-boot-starter-security')

        dependencies.extend(['h2', 'postgresql'])

        dependencies.extend(['lombok', 'springdoc-openapi-starter-webmvc-ui'])
        
        return dependencies

    
    def _to_snake_case(self, text: str) -> str:
        """Convert text to snake_case."""
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', text).lower()
    
    def _to_kebab_case(self, text: str) -> str:
        """Convert text to kebab-case."""
        return re.sub('([a-z0-9])([A-Z])', r'\1-\2', text).lower()
    
    def _is_one_to_one(self, source_mult: str, target_mult: str) -> bool:
        return source_mult in ['1', '0..1'] and target_mult in ['1', '0..1']
    
    def _is_one_to_many(self, source_mult: str, target_mult: str) -> bool:
        return source_mult in ['1', '0..1'] and target_mult in ['0..*', '1..*', '*']
    
    def _is_many_to_one(self, source_mult: str, target_mult: str) -> bool:
        return source_mult in ['0..*', '1..*', '*'] and target_mult in ['1', '0..1']
    
    def _is_many_to_many(self, source_mult: str, target_mult: str) -> bool:
        return source_mult in ['0..*', '1..*', '*'] and target_mult in ['0..*', '1..*', '*']
    
    def _determine_cascade_types(self, relationship_type: str) -> List[str]:
        """Determine JPA cascade types based on relationship."""
        if relationship_type == 'COMPOSITION':
            return ['CascadeType.ALL']
        elif relationship_type == 'AGGREGATION':
            return ['CascadeType.PERSIST', 'CascadeType.MERGE']
        else:
            return []
    
    def _generate_join_column_name(self, rel_data: Dict) -> str:
        """Generate join column name for relationship."""
        target_class = rel_data.get('target_class_name', 'target')
        return f"{self._to_snake_case(target_class)}_id"
    
    def _generate_mapped_by(self, rel_data: Dict) -> str:
        """Generate mappedBy value for bidirectional relationships."""
        source_role = rel_data.get('source_role', '')
        if source_role:
            return source_role
        
        source_class = rel_data.get('source_class_name', 'source')
        return self._to_snake_case(source_class)
    
    def _generate_field_name(self, class_name: str, multiplicity: str) -> str:
        """Generate field name based on class name and multiplicity."""
        base_name = self._to_snake_case(class_name)
        
        if multiplicity in ['0..*', '1..*', '*']:
            return f"{base_name}s"  # Pluralize for collections
        else:
            return base_name
    
    def _determine_column_length(self, attr_type: str) -> Optional[int]:
        """Determine column length based on type."""
        if 'string' in attr_type.lower():
            return 255  # Default string length
        return None
    
    def _determine_precision(self, attr_type: str) -> Optional[int]:
        """Determine precision for numeric types."""
        if 'decimal' in attr_type.lower():
            return 19
        return None
    
    def _determine_scale(self, attr_type: str) -> Optional[int]:
        """Determine scale for decimal types."""
        if 'decimal' in attr_type.lower():
            return 2
        return None
