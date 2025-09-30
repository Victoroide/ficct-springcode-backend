"""
SpringBoot REST Controller Generator for creating REST API controllers from UML entities.
"""

import os
from typing import Dict, List
from .template_rendering_service import TemplateRenderingService


class SpringBootControllerGenerator:
    """
    Generator for SpringBoot REST Controller classes from UML entity definitions.
    """
    
    def __init__(self):
        self.template_renderer = TemplateRenderingService()
    
    def generate_controllers(self, uml_data: Dict, workspace_path: str, 
                           config: Dict) -> List[Dict]:
        """
        Generate REST controller classes for all entities.
        
        Args:
            uml_data: Parsed UML diagram data
            workspace_path: Project workspace directory
            config: SpringBoot configuration
            
        Returns:
            List of generated controller file information
        """
        generated_files = []
        
        for class_data in uml_data['classes']:
            if self._should_generate_controller(class_data):
                controller_file = self._generate_controller_class(
                    class_data, workspace_path, config, uml_data
                )
                generated_files.append(controller_file)
        
        return generated_files
    
    def _should_generate_controller(self, class_data: Dict) -> bool:
        """Determine if entity should have REST controller."""
        return (class_data['class_type'] != 'INTERFACE' and 
                class_data['springboot_mapping']['is_entity'] and
                class_data['springboot_mapping']['requires_crud'])
    
    def _generate_controller_class(self, class_data: Dict, workspace_path: str, 
                                 config: Dict, uml_data: Dict) -> Dict:
        """Generate individual REST controller class."""

        context = self._build_controller_context(class_data, config, uml_data)

        controller_content = self.template_renderer.render_controller_template(context)

        package_path = config['group_id'].replace('.', '/') + '/controllers'
        controller_name = class_data['springboot_mapping']['controller_name']
        file_path = os.path.join(workspace_path, 'src/main/java', package_path, f"{controller_name}.java")

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(controller_content)

        lines_count = len(controller_content.split('\n'))
        file_size = len(controller_content.encode('utf-8'))
        
        return {
            'type': 'controller',
            'class_name': controller_name,
            'entity_class': class_data['name'],
            'file_path': file_path,
            'relative_path': f"src/main/java/{package_path}/{controller_name}.java",
            'content': controller_content,
            'size': file_size,
            'lines_of_code': lines_count,
            'extension': '.java',
            'template_used': 'controller'
        }
    
    def _build_controller_context(self, class_data: Dict, config: Dict, 
                                uml_data: Dict) -> Dict:
        """Build template context for controller generation."""
        
        entity_name = class_data['name']
        controller_name = class_data['springboot_mapping']['controller_name']
        service_name = class_data['springboot_mapping']['service_name']
        dto_name = class_data['springboot_mapping']['dto_name']
        api_path = class_data['springboot_mapping']['api_path']
        id_type = self._determine_id_type(class_data)
        
        context = {
            'controller_name': controller_name,
            'entity_name': entity_name,
            'service_name': service_name,
            'dto_name': dto_name,
            'api_path': api_path,
            'id_type': id_type,
            'package_name': f"{config['group_id']}.controllers",
            'service_package': f"{config['group_id']}.services",
            'dto_package': f"{config['group_id']}.dto",
            'imports': self._generate_imports(class_data, config),
            'class_annotations': self._generate_class_annotations(class_data),
            'crud_endpoints': self._generate_crud_endpoints(class_data),
            'custom_endpoints': self._generate_custom_endpoints(class_data, uml_data),
            'search_endpoints': self._generate_search_endpoints(class_data),
            'exception_handlers': self._generate_exception_handlers(class_data)
        }
        
        return context
    
    def _determine_id_type(self, class_data: Dict) -> str:
        """Determine the ID type for the entity."""
        for attr in class_data['attributes']:
            if attr['name'].lower() == 'id':
                return attr['java_type']
        return 'Long'
    
    def _generate_imports(self, class_data: Dict, config: Dict) -> List[str]:
        """Generate required imports for controller class."""
        imports = [
            'org.springframework.beans.factory.annotation.Autowired',
            'org.springframework.web.bind.annotation.*',
            'org.springframework.http.HttpStatus',
            'org.springframework.http.ResponseEntity',
            'java.util.List',
            'java.util.Optional'
        ]

        service_name = class_data['springboot_mapping']['service_name']
        dto_name = class_data['springboot_mapping']['dto_name']
        
        imports.extend([
            f"{config['group_id']}.services.{service_name}",
            f"{config['group_id']}.dto.{dto_name}"
        ])

        imports.extend([
            'javax.validation.Valid',
            'javax.validation.constraints.*'
        ])

        if self._needs_pagination_support(class_data):
            imports.extend([
                'org.springframework.data.domain.Page',
                'org.springframework.data.domain.Pageable',
                'org.springframework.data.web.PageableDefault'
            ])

        imports.extend([
            'io.swagger.v3.oas.annotations.Operation',
            'io.swagger.v3.oas.annotations.Parameter',
            'io.swagger.v3.oas.annotations.responses.ApiResponse',
            'io.swagger.v3.oas.annotations.responses.ApiResponses',
            'io.swagger.v3.oas.annotations.tags.Tag'
        ])

        id_type = self._determine_id_type(class_data)
        if id_type == 'UUID':
            imports.append('java.util.UUID')

        imports.extend([
            'org.springframework.web.bind.annotation.ExceptionHandler',
            'java.util.NoSuchElementException',
            'org.springframework.dao.DataIntegrityViolationException'
        ])
        
        return sorted(list(set(imports)))
    
    def _generate_class_annotations(self, class_data: Dict) -> List[str]:
        """Generate class-level annotations for controller."""
        entity_name = class_data['name']
        api_path = class_data['springboot_mapping']['api_path']
        
        annotations = [
            '@RestController',
            f'@RequestMapping("/api/v1/{api_path}")',
            '@CrossOrigin(origins = "*")',
            f'@Tag(name = "{entity_name} Controller", description = "REST API for {entity_name} operations")'
        ]
        
        return annotations
    
    def _generate_crud_endpoints(self, class_data: Dict) -> List[Dict]:
        """Generate standard CRUD REST endpoints."""
        entity_name = class_data['name']
        dto_name = class_data['springboot_mapping']['dto_name']
        id_type = self._determine_id_type(class_data)
        service_field = f"{entity_name.lower()}Service"
        
        crud_endpoints = [
            {
                'method': 'POST',
                'path': '',
                'name': f'create{entity_name}',
                'return_type': f'ResponseEntity<{dto_name}>',
                'parameters': [
                    {'type': dto_name, 'name': f'{entity_name.lower()}DTO', 'annotation': '@Valid @RequestBody'}
                ],
                'annotations': [
                    '@PostMapping',
                    f'@Operation(summary = "Create a new {entity_name}")',
                    '@ApiResponses(value = {',
                    '    @ApiResponse(responseCode = "201", description = "Successfully created"),',
                    '    @ApiResponse(responseCode = "400", description = "Invalid input")',
                    '})'
                ],
                'implementation': f'''
        {dto_name} created{entity_name} = {service_field}.create{entity_name}({entity_name.lower()}DTO);
        return new ResponseEntity<>(created{entity_name}, HttpStatus.CREATED);'''
            },
            {
                'method': 'GET',
                'path': '/{id}',
                'name': f'get{entity_name}ById',
                'return_type': f'ResponseEntity<{dto_name}>',
                'parameters': [
                    {'type': id_type, 'name': 'id', 'annotation': '@PathVariable'}
                ],
                'annotations': [
                    '@GetMapping("/{id}")',
                    f'@Operation(summary = "Get {entity_name} by ID")',
                    '@ApiResponses(value = {',
                    '    @ApiResponse(responseCode = "200", description = "Successfully retrieved"),',
                    '    @ApiResponse(responseCode = "404", description = "Entity not found")',
                    '})'
                ],
                'implementation': f'''
        {dto_name} {entity_name.lower()} = {service_field}.get{entity_name}ById(id);
        return ResponseEntity.ok({entity_name.lower()});'''
            },
            {
                'method': 'GET',
                'path': '',
                'name': f'getAll{entity_name}s',
                'return_type': f'ResponseEntity<List<{dto_name}>>',
                'parameters': [],
                'annotations': [
                    '@GetMapping',
                    f'@Operation(summary = "Get all {entity_name}s")',
                    '@ApiResponse(responseCode = "200", description = "Successfully retrieved")'
                ],
                'implementation': f'''
        List<{dto_name}> {entity_name.lower()}s = {service_field}.getAll{entity_name}s();
        return ResponseEntity.ok({entity_name.lower()}s);'''
            },
            {
                'method': 'PUT',
                'path': '/{id}',
                'name': f'update{entity_name}',
                'return_type': f'ResponseEntity<{dto_name}>',
                'parameters': [
                    {'type': id_type, 'name': 'id', 'annotation': '@PathVariable'},
                    {'type': dto_name, 'name': f'{entity_name.lower()}DTO', 'annotation': '@Valid @RequestBody'}
                ],
                'annotations': [
                    '@PutMapping("/{id}")',
                    f'@Operation(summary = "Update {entity_name}")',
                    '@ApiResponses(value = {',
                    '    @ApiResponse(responseCode = "200", description = "Successfully updated"),',
                    '    @ApiResponse(responseCode = "404", description = "Entity not found"),',
                    '    @ApiResponse(responseCode = "400", description = "Invalid input")',
                    '})'
                ],
                'implementation': f'''
        {dto_name} updated{entity_name} = {service_field}.update{entity_name}(id, {entity_name.lower()}DTO);
        return ResponseEntity.ok(updated{entity_name});'''
            },
            {
                'method': 'DELETE',
                'path': '/{id}',
                'name': f'delete{entity_name}',
                'return_type': 'ResponseEntity<Void>',
                'parameters': [
                    {'type': id_type, 'name': 'id', 'annotation': '@PathVariable'}
                ],
                'annotations': [
                    '@DeleteMapping("/{id}")',
                    f'@Operation(summary = "Delete {entity_name}")',
                    '@ApiResponses(value = {',
                    '    @ApiResponse(responseCode = "204", description = "Successfully deleted"),',
                    '    @ApiResponse(responseCode = "404", description = "Entity not found")',
                    '})'
                ],
                'implementation': f'''
        {service_field}.delete{entity_name}(id);
        return ResponseEntity.noContent().build();'''
            }
        ]

        if self._needs_pagination_support(class_data):
            crud_endpoints.append({
                'method': 'GET',
                'path': '/page',
                'name': f'get{entity_name}sWithPagination',
                'return_type': f'ResponseEntity<Page<{dto_name}>>',
                'parameters': [
                    {'type': 'Pageable', 'name': 'pageable', 'annotation': '@PageableDefault(size = 20, sort = "id")'}
                ],
                'annotations': [
                    '@GetMapping("/page")',
                    f'@Operation(summary = "Get {entity_name}s with pagination")',
                    '@ApiResponse(responseCode = "200", description = "Successfully retrieved")'
                ],
                'implementation': f'''
        Page<{dto_name}> {entity_name.lower()}Page = {service_field}.get{entity_name}sWithPagination(pageable);
        return ResponseEntity.ok({entity_name.lower()}Page);'''
            })
        
        return crud_endpoints
    
    def _generate_custom_endpoints(self, class_data: Dict, uml_data: Dict) -> List[Dict]:
        """Generate custom endpoints based on entity attributes."""
        custom_endpoints = []
        entity_name = class_data['name']
        dto_name = class_data['springboot_mapping']['dto_name']
        service_field = f"{entity_name.lower()}Service"

        for attr in class_data['attributes']:
            if self._should_generate_finder_endpoint(attr):
                attr_name = attr['name']
                attr_type = attr['java_type']
                
                custom_endpoints.append({
                    'method': 'GET',
                    'path': f'/by-{self._to_kebab_case(attr_name)}/{{value}}',
                    'name': f'get{entity_name}By{attr_name.title()}',
                    'return_type': f'ResponseEntity<{dto_name}>',
                    'parameters': [
                        {'type': attr_type, 'name': 'value', 'annotation': '@PathVariable'}
                    ],
                    'annotations': [
                        f'@GetMapping("/by-{self._to_kebab_case(attr_name)}/{{value}}")',
                        f'@Operation(summary = "Get {entity_name} by {attr_name}")',
                        '@ApiResponses(value = {',
                        '    @ApiResponse(responseCode = "200", description = "Successfully retrieved"),',
                        '    @ApiResponse(responseCode = "404", description = "Entity not found")',
                        '})'
                    ],
                    'implementation': f'''
        Optional<{dto_name}> {entity_name.lower()} = {service_field}.get{entity_name}By{attr_name.title()}(value);
        return {entity_name.lower()}.map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());'''
                })

        status_attrs = [attr for attr in class_data['attributes'] 
                       if any(status_word in attr['name'].lower() 
                             for status_word in ['status', 'active', 'enabled', 'state'])]
        
        for attr in status_attrs:
            custom_endpoints.append({
                'method': 'GET',
                'path': '/active',
                'name': f'getActive{entity_name}s',
                'return_type': f'ResponseEntity<List<{dto_name}>>',
                'parameters': [],
                'annotations': [
                    '@GetMapping("/active")',
                    f'@Operation(summary = "Get all active {entity_name}s")',
                    '@ApiResponse(responseCode = "200", description = "Successfully retrieved")'
                ],
                'implementation': f'''
        List<{dto_name}> active{entity_name}s = {service_field}.getActive{entity_name}s();
        return ResponseEntity.ok(active{entity_name}s);'''
            })
            break  # Only generate one active endpoint
        
        return custom_endpoints
    
    def _generate_search_endpoints(self, class_data: Dict) -> List[Dict]:
        """Generate search endpoints for string attributes."""
        search_endpoints = []
        entity_name = class_data['name']
        dto_name = class_data['springboot_mapping']['dto_name']
        service_field = f"{entity_name.lower()}Service"

        string_attrs = [attr for attr in class_data['attributes'] 
                       if 'String' in attr['java_type'] and attr['name'].lower() != 'id']
        
        for attr in string_attrs:
            attr_name = attr['name']
            
            search_endpoints.append({
                'method': 'GET',
                'path': f'/search/{self._to_kebab_case(attr_name)}',
                'name': f'search{entity_name}By{attr_name.title()}',
                'return_type': f'ResponseEntity<List<{dto_name}>>',
                'parameters': [
                    {'type': 'String', 'name': 'searchTerm', 'annotation': '@RequestParam'}
                ],
                'annotations': [
                    f'@GetMapping("/search/{self._to_kebab_case(attr_name)}")',
                    f'@Operation(summary = "Search {entity_name} by {attr_name}")',
                    '@ApiResponse(responseCode = "200", description = "Successfully retrieved")'
                ],
                'implementation': f'''
        List<{dto_name}> results = {service_field}.search{entity_name}By{attr_name.title()}(searchTerm);
        return ResponseEntity.ok(results);'''
            })
        
        return search_endpoints
    
    def _generate_exception_handlers(self, class_data: Dict) -> List[Dict]:
        """Generate exception handler methods."""
        exception_handlers = [
            {
                'exception': 'NoSuchElementException',
                'method_name': 'handleNotFound',
                'return_type': 'ResponseEntity<String>',
                'response_status': 'HttpStatus.NOT_FOUND',
                'implementation': '''
        return new ResponseEntity<>(ex.getMessage(), HttpStatus.NOT_FOUND);'''
            },
            {
                'exception': 'DataIntegrityViolationException',
                'method_name': 'handleDataIntegrityViolation',
                'return_type': 'ResponseEntity<String>',
                'response_status': 'HttpStatus.CONFLICT',
                'implementation': '''
        return new ResponseEntity<>("Data integrity violation: " + ex.getMessage(), HttpStatus.CONFLICT);'''
            },
            {
                'exception': 'IllegalArgumentException',
                'method_name': 'handleIllegalArgument',
                'return_type': 'ResponseEntity<String>',
                'response_status': 'HttpStatus.BAD_REQUEST',
                'implementation': '''
        return new ResponseEntity<>("Invalid argument: " + ex.getMessage(), HttpStatus.BAD_REQUEST);'''
            }
        ]
        
        return exception_handlers
    
    def _should_generate_finder_endpoint(self, attr: Dict) -> bool:
        """Determine if attribute should have finder endpoint."""
        attr_name = attr['name'].lower()
        unique_identifiers = ['email', 'username', 'code', 'reference', 'slug', 'key']
        return any(identifier in attr_name for identifier in unique_identifiers)
    
    def _needs_pagination_support(self, class_data: Dict) -> bool:
        """Check if entity needs pagination support."""
        searchable_attrs = [attr for attr in class_data['attributes']
                          if 'String' in attr['java_type'] or 
                             any(status in attr['name'].lower() 
                                 for status in ['status', 'type', 'category'])]
        return len(searchable_attrs) >= 2
    
    def _to_kebab_case(self, text: str) -> str:
        """Convert text to kebab-case."""
        import re
        return re.sub('([a-z0-9])([A-Z])', r'\1-\2', text).lower()
