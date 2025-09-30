"""
SpringBoot JPA Repository Generator for creating repository interfaces from UML entities.
"""

import os
from typing import Dict, List
from .template_rendering_service import TemplateRenderingService


class SpringBootRepositoryGenerator:
    """
    Generator for SpringBoot JPA Repository interfaces from UML entity definitions.
    """
    
    def __init__(self):
        self.template_renderer = TemplateRenderingService()
    
    def generate_repositories(self, uml_data: Dict, workspace_path: str, 
                            config: Dict) -> List[Dict]:
        """
        Generate JPA repository interfaces for all entities.
        
        Args:
            uml_data: Parsed UML diagram data
            workspace_path: Project workspace directory
            config: SpringBoot configuration
            
        Returns:
            List of generated repository file information
        """
        generated_files = []
        
        for class_data in uml_data['classes']:
            if self._should_generate_repository(class_data):
                repository_file = self._generate_repository_interface(
                    class_data, workspace_path, config, uml_data
                )
                generated_files.append(repository_file)
        
        return generated_files
    
    def _should_generate_repository(self, class_data: Dict) -> bool:
        """Determine if entity should have repository interface."""
        return (class_data['class_type'] != 'INTERFACE' and 
                class_data['springboot_mapping']['is_entity'] and
                class_data['springboot_mapping']['requires_crud'])
    
    def _generate_repository_interface(self, class_data: Dict, workspace_path: str, 
                                     config: Dict, uml_data: Dict) -> Dict:
        """Generate individual JPA repository interface."""

        context = self._build_repository_context(class_data, config, uml_data)

        repository_content = self.template_renderer.render_repository_template(context)

        package_path = config['group_id'].replace('.', '/') + '/repositories'
        repository_name = class_data['springboot_mapping']['repository_name']
        file_path = os.path.join(workspace_path, 'src/main/java', package_path, f"{repository_name}.java")

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(repository_content)

        lines_count = len(repository_content.split('\n'))
        file_size = len(repository_content.encode('utf-8'))
        
        return {
            'type': 'repository',
            'class_name': repository_name,
            'entity_class': class_data['name'],
            'file_path': file_path,
            'relative_path': f"src/main/java/{package_path}/{repository_name}.java",
            'content': repository_content,
            'size': file_size,
            'lines_of_code': lines_count,
            'extension': '.java',
            'template_used': 'repository'
        }
    
    def _build_repository_context(self, class_data: Dict, config: Dict, 
                                uml_data: Dict) -> Dict:
        """Build template context for repository generation."""
        
        entity_name = class_data['name']
        repository_name = class_data['springboot_mapping']['repository_name']
        id_type = self._determine_id_type(class_data)
        
        context = {
            'repository_name': repository_name,
            'entity_name': entity_name,
            'id_type': id_type,
            'package_name': f"{config['group_id']}.repositories",
            'entity_package': f"{config['group_id']}.entities",
            'imports': self._generate_imports(class_data, id_type),
            'custom_methods': self._generate_custom_methods(class_data, uml_data),
            'query_methods': self._generate_query_methods(class_data),
            'native_queries': self._generate_native_queries(class_data)
        }
        
        return context
    
    def _determine_id_type(self, class_data: Dict) -> str:
        """Determine the ID type for the entity."""
        for attr in class_data['attributes']:
            if attr['name'].lower() == 'id':
                return attr['java_type']
        
        return 'Long'  # Default ID type
    
    def _generate_imports(self, class_data: Dict, id_type: str) -> List[str]:
        """Generate required imports for repository interface."""
        imports = [
            'org.springframework.data.jpa.repository.JpaRepository',
            'org.springframework.stereotype.Repository'
        ]

        if self._has_custom_queries(class_data):
            imports.extend([
                'org.springframework.data.jpa.repository.Query',
                'org.springframework.data.repository.query.Param'
            ])

        if self._has_pagination_methods(class_data):
            imports.extend([
                'org.springframework.data.domain.Page',
                'org.springframework.data.domain.Pageable'
            ])

        imports.append('java.util.Optional')

        imports.append('java.util.List')

        if id_type == 'UUID':
            imports.append('java.util.UUID')
        
        return sorted(list(set(imports)))
    
    def _generate_custom_methods(self, class_data: Dict, uml_data: Dict) -> List[Dict]:
        """Generate custom finder methods based on entity attributes."""
        custom_methods = []
        
        for attr in class_data['attributes']:
            attr_name = attr['name']
            attr_type = attr['java_type']

            if attr_name.lower() == 'id':
                continue

            if self._should_generate_finder_method(attr):
                method_name = f"findBy{attr_name.title()}"
                
                custom_methods.append({
                    'name': method_name,
                    'return_type': f"Optional<{class_data['name']}>",
                    'parameters': [{'type': attr_type, 'name': attr_name}],
                    'query_annotation': None,
                    'description': f"Find {class_data['name']} by {attr_name}"
                })

                exists_method_name = f"existsBy{attr_name.title()}"
                custom_methods.append({
                    'name': exists_method_name,
                    'return_type': 'boolean',
                    'parameters': [{'type': attr_type, 'name': attr_name}],
                    'query_annotation': None,
                    'description': f"Check if {class_data['name']} exists by {attr_name}"
                })

                delete_method_name = f"deleteBy{attr_name.title()}"
                custom_methods.append({
                    'name': delete_method_name,
                    'return_type': 'void',
                    'parameters': [{'type': attr_type, 'name': attr_name}],
                    'query_annotation': None,
                    'description': f"Delete {class_data['name']} by {attr_name}"
                })
        
        return custom_methods
    
    def _generate_query_methods(self, class_data: Dict) -> List[Dict]:
        """Generate query methods with JPQL."""
        query_methods = []

        string_attrs = [attr for attr in class_data['attributes'] 
                       if 'String' in attr['java_type'] and attr['name'].lower() != 'id']
        
        for attr in string_attrs:
            attr_name = attr['name']

            method_name = f"findBy{attr_name.title()}IgnoreCase"
            jpql_query = f"SELECT e FROM {class_data['name']} e WHERE LOWER(e.{attr_name}) = LOWER(?1)"
            
            query_methods.append({
                'name': method_name,
                'return_type': f"List<{class_data['name']}>",
                'parameters': [{'type': 'String', 'name': attr_name}],
                'query_annotation': f'@Query("{jpql_query}")',
                'description': f"Find {class_data['name']} by {attr_name} (case-insensitive)"
            })

            contains_method_name = f"findBy{attr_name.title()}Containing"
            query_methods.append({
                'name': contains_method_name,
                'return_type': f"List<{class_data['name']}>",
                'parameters': [{'type': 'String', 'name': attr_name}],
                'query_annotation': None,
                'description': f"Find {class_data['name']} containing {attr_name}"
            })

        status_attrs = [attr for attr in class_data['attributes'] 
                       if any(status_word in attr['name'].lower() 
                             for status_word in ['status', 'active', 'enabled', 'state'])]
        
        for attr in status_attrs:
            method_name = f"findBy{attr['name'].title()}True"
            
            query_methods.append({
                'name': method_name,
                'return_type': f"List<{class_data['name']}>",
                'parameters': [],
                'query_annotation': None,
                'description': f"Find active {class_data['name']} records"
            })
        
        return query_methods
    
    def _generate_native_queries(self, class_data: Dict) -> List[Dict]:
        """Generate native SQL queries for complex operations."""
        native_queries = []

        has_status = any('status' in attr['name'].lower() for attr in class_data['attributes'])
        
        if has_status:
            table_name = class_data['springboot_mapping']['table_name']
            
            native_queries.append({
                'name': 'countByStatus',
                'return_type': 'Long',
                'parameters': [{'type': 'String', 'name': 'status'}],
                'query_annotation': f'@Query(value = "SELECT COUNT(*) FROM {table_name} WHERE status = ?1", nativeQuery = true)',
                'description': f"Count {class_data['name']} by status using native SQL"
            })

        updatable_attrs = [attr for attr in class_data['attributes']
                          if attr['name'].lower() not in ['id', 'created_at', 'created_date']]
        
        if len(updatable_attrs) > 0:

            if has_status:
                table_name = class_data['springboot_mapping']['table_name']
                
                native_queries.append({
                    'name': 'updateStatusByIds',
                    'return_type': 'int',
                    'parameters': [
                        {'type': 'String', 'name': 'status'},
                        {'type': 'List<Long>', 'name': 'ids'}
                    ],
                    'query_annotation': f'@Query(value = "UPDATE {table_name} SET status = ?1 WHERE id IN ?2", nativeQuery = true)',
                    'modifying': True,
                    'description': f"Bulk update status for multiple {class_data['name']} records"
                })
        
        return native_queries
    
    def _should_generate_finder_method(self, attr: Dict) -> bool:
        """Determine if attribute should have finder methods."""
        attr_name = attr['name'].lower()

        unique_identifiers = ['email', 'username', 'code', 'reference', 'slug', 'key']
        if any(identifier in attr_name for identifier in unique_identifiers):
            return True

        status_fields = ['status', 'state', 'type', 'category']
        if any(field in attr_name for field in status_fields):
            return True

        if attr_name.endswith('_id') or attr_name.endswith('id'):
            return True
        
        return False
    
    def _has_custom_queries(self, class_data: Dict) -> bool:
        """Check if entity requires custom JPQL queries."""

        string_attrs = [attr for attr in class_data['attributes'] if 'String' in attr['java_type']]
        return len(string_attrs) > 1  # More than just basic string fields
    
    def _has_pagination_methods(self, class_data: Dict) -> bool:
        """Check if entity should have pagination support."""

        searchable_attrs = [attr for attr in class_data['attributes']
                          if 'String' in attr['java_type'] or 
                             any(status in attr['name'].lower() 
                                 for status in ['status', 'type', 'category'])]
        
        return len(searchable_attrs) >= 2
