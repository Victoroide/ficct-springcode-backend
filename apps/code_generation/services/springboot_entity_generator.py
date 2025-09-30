"""
SpringBoot JPA Entity Generator for converting UML classes to Java entity classes.
"""

import os
from typing import Dict, List
from .template_rendering_service import TemplateRenderingService


class SpringBootEntityGenerator:
    """
    Generator for SpringBoot JPA Entity classes from UML class definitions.
    """
    
    def __init__(self):
        self.template_renderer = TemplateRenderingService()
    
    def generate_entities(self, uml_data: Dict, workspace_path: str, 
                         config: Dict) -> List[Dict]:
        """
        Generate JPA entity classes for all UML classes.
        
        Args:
            uml_data: Parsed UML diagram data
            workspace_path: Project workspace directory
            config: SpringBoot configuration
            
        Returns:
            List of generated file information
        """
        generated_files = []
        
        for class_data in uml_data['classes']:
            if self._should_generate_entity(class_data):
                entity_file = self._generate_entity_class(
                    class_data, workspace_path, config, uml_data['relationship_mappings']
                )
                generated_files.append(entity_file)
        
        return generated_files
    
    def _should_generate_entity(self, class_data: Dict) -> bool:
        """Determine if UML class should become JPA entity."""

        if class_data['class_type'] in ['INTERFACE']:
            return False

        entity_indicators = ['entity', 'model', 'do', 'po']
        class_name_lower = class_data['name'].lower()
        stereotype_lower = class_data.get('stereotype', '').lower()
        
        return (any(indicator in class_name_lower for indicator in entity_indicators) or
                any(indicator in stereotype_lower for indicator in entity_indicators) or
                class_data['springboot_mapping']['is_entity'])
    
    def _generate_entity_class(self, class_data: Dict, workspace_path: str, 
                              config: Dict, relationship_mappings: Dict) -> Dict:
        """Generate individual JPA entity class."""

        context = self._build_entity_context(class_data, config, relationship_mappings)

        entity_content = self.template_renderer.render_entity_template(context)

        package_path = config['group_id'].replace('.', '/') + '/entities'
        file_path = os.path.join(workspace_path, 'src/main/java', package_path, f"{class_data['name']}.java")

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(entity_content)

        lines_count = len(entity_content.split('\n'))
        file_size = len(entity_content.encode('utf-8'))
        
        return {
            'type': 'entity',
            'class_name': class_data['name'],
            'file_path': file_path,
            'relative_path': f"src/main/java/{package_path}/{class_data['name']}.java",
            'content': entity_content,
            'size': file_size,
            'lines_of_code': lines_count,
            'extension': '.java',
            'template_used': 'entity'
        }
    
    def _build_entity_context(self, class_data: Dict, config: Dict, 
                             relationship_mappings: Dict) -> Dict:
        """Build template context for entity generation."""

        context = {
            'class_name': class_data['name'],
            'package_name': f"{config['group_id']}.entities",
            'table_name': class_data['springboot_mapping']['table_name'],
            'imports': self._generate_imports(class_data, relationship_mappings),
            'class_annotations': self._generate_class_annotations(class_data),
            'attributes': self._process_attributes(class_data['attributes']),
            'relationships': self._process_relationships(class_data, relationship_mappings),
            'constructors': self._generate_constructors(class_data),
            'methods': self._process_methods(class_data['methods'])
        }
        
        return context
    
    def _generate_imports(self, class_data: Dict, relationship_mappings: Dict) -> List[str]:
        """Generate required imports for entity class."""
        imports = [
            'javax.persistence.*',
            'java.util.Objects',
            'java.time.LocalDateTime'
        ]

        for attr in class_data['attributes']:
            java_type = attr['java_type']
            
            if 'LocalDate' in java_type:
                imports.append('java.time.LocalDate')
            elif 'LocalTime' in java_type:
                imports.append('java.time.LocalTime')
            elif 'BigDecimal' in java_type:
                imports.append('java.math.BigDecimal')
            elif 'UUID' in java_type:
                imports.append('java.util.UUID')
            elif 'List' in java_type or 'Set' in java_type:
                imports.extend(['java.util.List', 'java.util.Set', 'java.util.ArrayList', 'java.util.HashSet'])

        relationships = self._get_class_relationships(class_data['id'], relationship_mappings)
        if relationships:
            imports.extend([
                'javax.persistence.FetchType',
                'javax.persistence.CascadeType'
            ])

        has_validation = any('@NotNull' in attr.get('annotations', []) or 
                           '@NotBlank' in attr.get('annotations', []) 
                           for attr in class_data['attributes'])
        
        if has_validation:
            imports.extend([
                'javax.validation.constraints.*',
                'org.hibernate.validator.constraints.*'
            ])

        has_timestamps = any(attr['name'].lower() in ['created_at', 'updated_at'] 
                           for attr in class_data['attributes'])
        
        if has_timestamps:
            imports.extend([
                'org.hibernate.annotations.CreationTimestamp',
                'org.hibernate.annotations.UpdateTimestamp'
            ])
        
        return sorted(list(set(imports)))
    
    def _generate_class_annotations(self, class_data: Dict) -> List[str]:
        """Generate JPA class-level annotations."""
        annotations = ['@Entity']
        
        table_name = class_data['springboot_mapping']['table_name']
        if table_name != class_data['name'].lower():
            annotations.append(f'@Table(name = "{table_name}")')
        
        return annotations
    
    def _process_attributes(self, attributes: List[Dict]) -> List[Dict]:
        """Process attributes for template rendering."""
        processed_attrs = []
        
        for attr in attributes:
            processed_attr = {
                'name': attr['name'],
                'type': attr['java_type'],
                'annotations': self._enhance_attribute_annotations(attr),
                'visibility': attr['visibility'].lower(),
                'is_static': attr['is_static'],
                'is_final': attr['is_final'],
                'default_value': attr.get('default_value'),
                'getter_method': f"get{attr['name'].title()}",
                'setter_method': f"set{attr['name'].title()}",
                'documentation': attr.get('documentation', '')
            }
            
            processed_attrs.append(processed_attr)
        
        return processed_attrs
    
    def _enhance_attribute_annotations(self, attr: Dict) -> List[str]:
        """Enhance attribute annotations with JPA and validation."""
        annotations = attr.get('annotations', []).copy()

        jpa_mapping = attr.get('jpa_mapping', {})
        
        column_props = []
        if not jpa_mapping.get('is_nullable', True):
            column_props.append('nullable = false')
        
        if jpa_mapping.get('is_unique', False):
            column_props.append('unique = true')
        
        if jpa_mapping.get('length') and jpa_mapping['length'] != 255:
            column_props.append(f'length = {jpa_mapping["length"]}')
        
        if column_props:
            annotations.append(f'@Column({", ".join(column_props)})')
        
        return annotations
    
    def _process_relationships(self, class_data: Dict, relationship_mappings: Dict) -> List[Dict]:
        """Process relationships for the entity."""
        relationships = []
        class_relationships = self._get_class_relationships(class_data['id'], relationship_mappings)
        
        for rel_key, rel_data in class_relationships.items():
            if rel_data['source_class'] == class_data['name']:

                relationship = {
                    'field_name': rel_data['field_name_source'],
                    'target_class': rel_data['target_class'],
                    'jpa_annotation': f"@{rel_data['jpa_mapping']['jpa_annotation']}",
                    'fetch_type': rel_data['jpa_mapping']['fetch_type'],
                    'cascade_types': rel_data['jpa_mapping']['cascade_types'],
                    'join_column': rel_data['jpa_mapping'].get('join_column'),
                    'mapped_by': None,
                    'is_collection': 'Many' in rel_data['jpa_mapping']['jpa_annotation']
                }
                
                relationships.append(relationship)
            
            elif rel_data['target_class'] == class_data['name'] and rel_data['field_name_target']:

                relationship = {
                    'field_name': rel_data['field_name_target'],
                    'target_class': rel_data['source_class'],
                    'jpa_annotation': self._get_inverse_annotation(rel_data['jpa_mapping']['jpa_annotation']),
                    'fetch_type': rel_data['jpa_mapping']['fetch_type'],
                    'cascade_types': [],
                    'join_column': None,
                    'mapped_by': rel_data['field_name_source'],
                    'is_collection': 'Many' in self._get_inverse_annotation(rel_data['jpa_mapping']['jpa_annotation'])
                }
                
                relationships.append(relationship)
        
        return relationships
    
    def _get_class_relationships(self, class_id: str, relationship_mappings: Dict) -> Dict:
        """Get all relationships involving the specified class."""
        class_relationships = {}
        
        for rel_key, rel_data in relationship_mappings.items():
            if (rel_data.get('source_class_id') == class_id or 
                rel_data.get('target_class_id') == class_id):
                class_relationships[rel_key] = rel_data
        
        return class_relationships
    
    def _get_inverse_annotation(self, annotation: str) -> str:
        """Get inverse JPA annotation for bidirectional relationships."""
        inverse_map = {
            'OneToMany': 'ManyToOne',
            'ManyToOne': 'OneToMany',
            'OneToOne': 'OneToOne',
            'ManyToMany': 'ManyToMany'
        }
        return inverse_map.get(annotation, 'ManyToOne')
    
    def _generate_constructors(self, class_data: Dict) -> List[Dict]:
        """Generate constructor methods for entity."""
        constructors = []

        constructors.append({
            'type': 'default',
            'parameters': [],
            'body': '// Default constructor'
        })

        required_attrs = [attr for attr in class_data['attributes'] 
                         if attr['name'].lower() != 'id' and attr.get('is_final', False)]
        
        if required_attrs:
            constructor_params = []
            constructor_body = []
            
            for attr in required_attrs:
                constructor_params.append({
                    'type': attr['java_type'],
                    'name': attr['name']
                })
                constructor_body.append(f'this.{attr["name"]} = {attr["name"]};')
            
            constructors.append({
                'type': 'parameterized',
                'parameters': constructor_params,
                'body': '\n        '.join(constructor_body)
            })
        
        return constructors
    
    def _process_methods(self, methods: List[Dict]) -> List[Dict]:
        """Process custom methods for entity."""
        processed_methods = []
        
        for method in methods:

            if (method['name'].startswith('get') or method['name'].startswith('set') or
                method['name'].startswith('is')):
                continue
            
            processed_method = {
                'name': method['name'],
                'return_type': method['java_return_type'],
                'parameters': method['parameters'],
                'visibility': method['visibility'].lower(),
                'is_static': method['is_static'],
                'annotations': method.get('annotations', []),
                'body': f'// TODO: Implement {method["name"]} method',
                'documentation': method.get('documentation', '')
            }
            
            processed_methods.append(processed_method)
        
        return processed_methods
