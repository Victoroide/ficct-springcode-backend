"""
SpringBoot Service Generator for creating service classes from UML entities.
"""

import os
from typing import Dict, List
from .template_rendering_service import TemplateRenderingService


class SpringBootServiceGenerator:
    """
    Generator for SpringBoot Service classes from UML entity definitions.
    """
    
    def __init__(self):
        self.template_renderer = TemplateRenderingService()
    
    def generate_services(self, uml_data: Dict, workspace_path: str, 
                         config: Dict) -> List[Dict]:
        """
        Generate service classes for all entities.
        
        Args:
            uml_data: Parsed UML diagram data
            workspace_path: Project workspace directory
            config: SpringBoot configuration
            
        Returns:
            List of generated service file information
        """
        generated_files = []
        
        for class_data in uml_data['classes']:
            if self._should_generate_service(class_data):
                service_file = self._generate_service_class(
                    class_data, workspace_path, config, uml_data
                )
                generated_files.append(service_file)
        
        return generated_files
    
    def _should_generate_service(self, class_data: Dict) -> bool:
        """Determine if entity should have service class."""
        return (class_data['class_type'] != 'INTERFACE' and 
                class_data['springboot_mapping']['is_entity'] and
                class_data['springboot_mapping']['requires_crud'])
    
    def _generate_service_class(self, class_data: Dict, workspace_path: str, 
                               config: Dict, uml_data: Dict) -> Dict:
        """Generate individual service class."""
        
        # Prepare template context
        context = self._build_service_context(class_data, config, uml_data)
        
        # Render service template
        service_content = self.template_renderer.render_service_template(context)
        
        # Generate file path
        package_path = config['group_id'].replace('.', '/') + '/services'
        service_name = class_data['springboot_mapping']['service_name']
        file_path = os.path.join(workspace_path, 'src/main/java', package_path, f"{service_name}.java")
        
        # Write service file
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(service_content)
        
        # Calculate file statistics
        lines_count = len(service_content.split('\n'))
        file_size = len(service_content.encode('utf-8'))
        
        return {
            'type': 'service',
            'class_name': service_name,
            'entity_class': class_data['name'],
            'file_path': file_path,
            'relative_path': f"src/main/java/{package_path}/{service_name}.java",
            'content': service_content,
            'size': file_size,
            'lines_of_code': lines_count,
            'extension': '.java',
            'template_used': 'service'
        }
    
    def _build_service_context(self, class_data: Dict, config: Dict, 
                              uml_data: Dict) -> Dict:
        """Build template context for service generation."""
        
        entity_name = class_data['name']
        service_name = class_data['springboot_mapping']['service_name']
        repository_name = class_data['springboot_mapping']['repository_name']
        dto_name = class_data['springboot_mapping']['dto_name']
        id_type = self._determine_id_type(class_data)
        
        context = {
            'service_name': service_name,
            'entity_name': entity_name,
            'repository_name': repository_name,
            'dto_name': dto_name,
            'id_type': id_type,
            'package_name': f"{config['group_id']}.services",
            'entity_package': f"{config['group_id']}.entities",
            'repository_package': f"{config['group_id']}.repositories",
            'dto_package': f"{config['group_id']}.dto",
            'imports': self._generate_imports(class_data, config),
            'crud_methods': self._generate_crud_methods(class_data),
            'custom_methods': self._generate_custom_methods(class_data, uml_data),
            'validation_methods': self._generate_validation_methods(class_data),
            'dto_mapping_methods': self._generate_dto_mapping_methods(class_data)
        }
        
        return context
    
    def _determine_id_type(self, class_data: Dict) -> str:
        """Determine the ID type for the entity."""
        for attr in class_data['attributes']:
            if attr['name'].lower() == 'id':
                return attr['java_type']
        return 'Long'
    
    def _generate_imports(self, class_data: Dict, config: Dict) -> List[str]:
        """Generate required imports for service class."""
        imports = [
            'org.springframework.beans.factory.annotation.Autowired',
            'org.springframework.stereotype.Service',
            'org.springframework.transaction.annotation.Transactional',
            'java.util.List',
            'java.util.Optional'
        ]
        
        # Add entity and repository imports
        entity_name = class_data['name']
        repository_name = class_data['springboot_mapping']['repository_name']
        
        imports.extend([
            f"{config['group_id']}.entities.{entity_name}",
            f"{config['group_id']}.repositories.{repository_name}"
        ])
        
        # Add DTO imports
        dto_name = class_data['springboot_mapping']['dto_name']
        imports.append(f"{config['group_id']}.dto.{dto_name}")
        
        # Add validation imports if needed
        if self._has_validation_requirements(class_data):
            imports.extend([
                'javax.validation.Valid',
                'javax.validation.constraints.*'
            ])
        
        # Add exception imports
        imports.extend([
            'java.util.NoSuchElementException',
            'org.springframework.dao.DataIntegrityViolationException'
        ])
        
        # Add pagination imports if needed
        if self._needs_pagination_support(class_data):
            imports.extend([
                'org.springframework.data.domain.Page',
                'org.springframework.data.domain.Pageable'
            ])
        
        # Add UUID import if needed
        id_type = self._determine_id_type(class_data)
        if id_type == 'UUID':
            imports.append('java.util.UUID')
        
        return sorted(list(set(imports)))
    
    def _generate_crud_methods(self, class_data: Dict) -> List[Dict]:
        """Generate standard CRUD methods."""
        entity_name = class_data['name']
        dto_name = class_data['springboot_mapping']['dto_name']
        id_type = self._determine_id_type(class_data)
        
        crud_methods = [
            {
                'name': f'create{entity_name}',
                'return_type': dto_name,
                'parameters': [{'type': dto_name, 'name': f'{entity_name.lower()}DTO', 'annotation': '@Valid'}],
                'annotations': ['@Transactional'],
                'description': f'Create a new {entity_name}',
                'implementation': self._generate_create_implementation(class_data)
            },
            {
                'name': f'get{entity_name}ById',
                'return_type': dto_name,
                'parameters': [{'type': id_type, 'name': 'id'}],
                'annotations': ['@Transactional(readOnly = true)'],
                'description': f'Get {entity_name} by ID',
                'implementation': self._generate_get_by_id_implementation(class_data)
            },
            {
                'name': f'getAll{entity_name}s',
                'return_type': f'List<{dto_name}>',
                'parameters': [],
                'annotations': ['@Transactional(readOnly = true)'],
                'description': f'Get all {entity_name}s',
                'implementation': self._generate_get_all_implementation(class_data)
            },
            {
                'name': f'update{entity_name}',
                'return_type': dto_name,
                'parameters': [
                    {'type': id_type, 'name': 'id'},
                    {'type': dto_name, 'name': f'{entity_name.lower()}DTO', 'annotation': '@Valid'}
                ],
                'annotations': ['@Transactional'],
                'description': f'Update existing {entity_name}',
                'implementation': self._generate_update_implementation(class_data)
            },
            {
                'name': f'delete{entity_name}',
                'return_type': 'void',
                'parameters': [{'type': id_type, 'name': 'id'}],
                'annotations': ['@Transactional'],
                'description': f'Delete {entity_name} by ID',
                'implementation': self._generate_delete_implementation(class_data)
            }
        ]
        
        # Add pagination method if needed
        if self._needs_pagination_support(class_data):
            crud_methods.append({
                'name': f'get{entity_name}sWithPagination',
                'return_type': f'Page<{dto_name}>',
                'parameters': [{'type': 'Pageable', 'name': 'pageable'}],
                'annotations': ['@Transactional(readOnly = true)'],
                'description': f'Get {entity_name}s with pagination',
                'implementation': self._generate_pagination_implementation(class_data)
            })
        
        return crud_methods
    
    def _generate_custom_methods(self, class_data: Dict, uml_data: Dict) -> List[Dict]:
        """Generate custom business logic methods."""
        custom_methods = []
        entity_name = class_data['name']
        dto_name = class_data['springboot_mapping']['dto_name']
        
        # Generate finder methods for unique attributes
        for attr in class_data['attributes']:
            if self._should_generate_finder_method(attr):
                attr_name = attr['name']
                attr_type = attr['java_type']
                
                custom_methods.append({
                    'name': f'get{entity_name}By{attr_name.title()}',
                    'return_type': f'Optional<{dto_name}>',
                    'parameters': [{'type': attr_type, 'name': attr_name}],
                    'annotations': ['@Transactional(readOnly = true)'],
                    'description': f'Find {entity_name} by {attr_name}',
                    'implementation': f'''
        Optional<{entity_name}> entity = {entity_name.lower()}Repository.findBy{attr_name.title()}({attr_name});
        return entity.map(this::convertToDTO);'''
                })
        
        # Generate search methods for string attributes
        string_attrs = [attr for attr in class_data['attributes'] 
                       if 'String' in attr['java_type'] and attr['name'].lower() != 'id']
        
        for attr in string_attrs:
            attr_name = attr['name']
            
            custom_methods.append({
                'name': f'search{entity_name}By{attr_name.title()}',
                'return_type': f'List<{dto_name}>',
                'parameters': [{'type': 'String', 'name': 'searchTerm'}],
                'annotations': ['@Transactional(readOnly = true)'],
                'description': f'Search {entity_name} by {attr_name}',
                'implementation': f'''
        List<{entity_name}> entities = {entity_name.lower()}Repository.findBy{attr_name.title()}Containing(searchTerm);
        return entities.stream().map(this::convertToDTO).collect(Collectors.toList());'''
            })
        
        # Generate status-based methods if applicable
        status_attrs = [attr for attr in class_data['attributes'] 
                       if any(status_word in attr['name'].lower() 
                             for status_word in ['status', 'active', 'enabled', 'state'])]
        
        for attr in status_attrs:
            custom_methods.append({
                'name': f'getActive{entity_name}s',
                'return_type': f'List<{dto_name}>',
                'parameters': [],
                'annotations': ['@Transactional(readOnly = true)'],
                'description': f'Get all active {entity_name}s',
                'implementation': f'''
        List<{entity_name}> entities = {entity_name.lower()}Repository.findBy{attr['name'].title()}True();
        return entities.stream().map(this::convertToDTO).collect(Collectors.toList());'''
            })
        
        return custom_methods
    
    def _generate_validation_methods(self, class_data: Dict) -> List[Dict]:
        """Generate validation methods for business rules."""
        validation_methods = []
        entity_name = class_data['name']
        
        # Generate unique constraint validation
        unique_attrs = [attr for attr in class_data['attributes']
                       if any(unique_field in attr['name'].lower() 
                             for unique_field in ['email', 'username', 'code', 'reference'])]
        
        for attr in unique_attrs:
            attr_name = attr['name']
            attr_type = attr['java_type']
            
            validation_methods.append({
                'name': f'validate{attr_name.title()}Uniqueness',
                'return_type': 'boolean',
                'parameters': [
                    {'type': attr_type, 'name': attr_name},
                    {'type': self._determine_id_type(class_data), 'name': 'excludeId', 'optional': True}
                ],
                'annotations': ['@Transactional(readOnly = true)'],
                'description': f'Validate {attr_name} uniqueness',
                'implementation': f'''
        if (excludeId != null) {{
            return !{entity_name.lower()}Repository.existsBy{attr_name.title()}AndIdNot({attr_name}, excludeId);
        }}
        return !{entity_name.lower()}Repository.existsBy{attr_name.title()}({attr_name});'''
            })
        
        return validation_methods
    
    def _generate_dto_mapping_methods(self, class_data: Dict) -> List[Dict]:
        """Generate DTO mapping methods."""
        entity_name = class_data['name']
        dto_name = class_data['springboot_mapping']['dto_name']
        
        mapping_methods = [
            {
                'name': 'convertToDTO',
                'return_type': dto_name,
                'parameters': [{'type': entity_name, 'name': 'entity'}],
                'annotations': [],
                'description': f'Convert {entity_name} entity to DTO',
                'implementation': self._generate_entity_to_dto_mapping(class_data)
            },
            {
                'name': 'convertToEntity',
                'return_type': entity_name,
                'parameters': [{'type': dto_name, 'name': 'dto'}],
                'annotations': [],
                'description': f'Convert DTO to {entity_name} entity',
                'implementation': self._generate_dto_to_entity_mapping(class_data)
            },
            {
                'name': 'updateEntityFromDTO',
                'return_type': 'void',
                'parameters': [
                    {'type': entity_name, 'name': 'entity'},
                    {'type': dto_name, 'name': 'dto'}
                ],
                'annotations': [],
                'description': f'Update entity from DTO',
                'implementation': self._generate_update_entity_mapping(class_data)
            }
        ]
        
        return mapping_methods
    
    def _generate_create_implementation(self, class_data: Dict) -> str:
        entity_name = class_data['name']
        return f'''
        {entity_name} entity = convertToEntity({entity_name.lower()}DTO);
        {entity_name} savedEntity = {entity_name.lower()}Repository.save(entity);
        return convertToDTO(savedEntity);'''
    
    def _generate_get_by_id_implementation(self, class_data: Dict) -> str:
        entity_name = class_data['name']
        return f'''
        {entity_name} entity = {entity_name.lower()}Repository.findById(id)
            .orElseThrow(() -> new NoSuchElementException("{entity_name} not found with id: " + id));
        return convertToDTO(entity);'''
    
    def _generate_get_all_implementation(self, class_data: Dict) -> str:
        entity_name = class_data['name']
        return f'''
        List<{entity_name}> entities = {entity_name.lower()}Repository.findAll();
        return entities.stream().map(this::convertToDTO).collect(Collectors.toList());'''
    
    def _generate_update_implementation(self, class_data: Dict) -> str:
        entity_name = class_data['name']
        return f'''
        {entity_name} existingEntity = {entity_name.lower()}Repository.findById(id)
            .orElseThrow(() -> new NoSuchElementException("{entity_name} not found with id: " + id));
        
        updateEntityFromDTO(existingEntity, {entity_name.lower()}DTO);
        {entity_name} updatedEntity = {entity_name.lower()}Repository.save(existingEntity);
        return convertToDTO(updatedEntity);'''
    
    def _generate_delete_implementation(self, class_data: Dict) -> str:
        entity_name = class_data['name']
        return f'''
        if (!{entity_name.lower()}Repository.existsById(id)) {{
            throw new NoSuchElementException("{entity_name} not found with id: " + id);
        }}
        {entity_name.lower()}Repository.deleteById(id);'''
    
    def _generate_pagination_implementation(self, class_data: Dict) -> str:
        entity_name = class_data['name']
        return f'''
        Page<{entity_name}> entityPage = {entity_name.lower()}Repository.findAll(pageable);
        return entityPage.map(this::convertToDTO);'''
    
    def _generate_entity_to_dto_mapping(self, class_data: Dict) -> str:
        entity_name = class_data['name']
        dto_name = class_data['springboot_mapping']['dto_name']
        
        mappings = []
        for attr in class_data['attributes']:
            attr_name = attr['name']
            mappings.append(f'        dto.set{attr_name.title()}(entity.get{attr_name.title()}());')
        
        return f'''
        {dto_name} dto = new {dto_name}();
{chr(10).join(mappings)}
        return dto;'''
    
    def _generate_dto_to_entity_mapping(self, class_data: Dict) -> str:
        entity_name = class_data['name']
        
        mappings = []
        for attr in class_data['attributes']:
            if attr['name'].lower() != 'id':  # Skip ID for new entities
                attr_name = attr['name']
                mappings.append(f'        entity.set{attr_name.title()}(dto.get{attr_name.title()}());')
        
        return f'''
        {entity_name} entity = new {entity_name}();
{chr(10).join(mappings)}
        return entity;'''
    
    def _generate_update_entity_mapping(self, class_data: Dict) -> str:
        mappings = []
        for attr in class_data['attributes']:
            if attr['name'].lower() not in ['id', 'created_at', 'created_date']:  # Skip immutable fields
                attr_name = attr['name']
                mappings.append(f'        entity.set{attr_name.title()}(dto.get{attr_name.title()}());')
        
        return chr(10).join(mappings) if mappings else '        // No updatable fields'
    
    def _should_generate_finder_method(self, attr: Dict) -> bool:
        """Determine if attribute should have finder methods."""
        attr_name = attr['name'].lower()
        unique_identifiers = ['email', 'username', 'code', 'reference', 'slug', 'key']
        return any(identifier in attr_name for identifier in unique_identifiers)
    
    def _has_validation_requirements(self, class_data: Dict) -> bool:
        """Check if entity requires validation."""
        return any('@NotNull' in attr.get('annotations', []) or 
                  '@NotBlank' in attr.get('annotations', []) 
                  for attr in class_data['attributes'])
    
    def _needs_pagination_support(self, class_data: Dict) -> bool:
        """Check if entity needs pagination support."""
        # Enable pagination for entities with multiple searchable fields
        searchable_attrs = [attr for attr in class_data['attributes']
                          if 'String' in attr['java_type'] or 
                             any(status in attr['name'].lower() 
                                 for status in ['status', 'type', 'category'])]
        return len(searchable_attrs) >= 2
