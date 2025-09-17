"""
Tests for SpringBoot code generators - Entity, Repository, Service, Controller.
"""

import unittest
from unittest.mock import Mock, patch, mock_open
from django.test import TestCase
import tempfile
import os

from ..services.springboot_entity_generator import SpringBootEntityGenerator
from ..services.springboot_repository_generator import SpringBootRepositoryGenerator
from ..services.springboot_service_generator import SpringBootServiceGenerator
from ..services.springboot_controller_generator import SpringBootControllerGenerator


class SpringBootEntityGeneratorTestCase(TestCase):
    """Test cases for SpringBootEntityGenerator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.generator = SpringBootEntityGenerator()
        self.sample_entity_data = {
            'class_name': 'User',
            'table_name': 'users',
            'package': 'com.example.entity',
            'attributes': [
                {
                    'name': 'id',
                    'java_type': 'Long',
                    'annotations': ['@Id', '@GeneratedValue(strategy = GenerationType.IDENTITY)']
                },
                {
                    'name': 'username',
                    'java_type': 'String',
                    'annotations': ['@Column(nullable = false, unique = true)', '@NotNull', '@Size(min = 3, max = 50)']
                }
            ],
            'relationships': [
                {
                    'type': 'OneToMany',
                    'field_name': 'orders',
                    'target_class': 'Order',
                    'annotations': ['@OneToMany(mappedBy = "user", cascade = CascadeType.ALL)']
                }
            ],
            'imports': [
                'javax.persistence.*',
                'javax.validation.constraints.*',
                'java.util.List'
            ],
            'annotations': ['@Entity', '@Table(name = "users")']
        }
    
    def test_generate_entity_content(self):
        """Test entity content generation."""
        content = self.generator.generate_entity_content(self.sample_entity_data)
        
        self.assertIn('package com.example.entity;', content)
        self.assertIn('import javax.persistence.*;', content)
        self.assertIn('@Entity', content)
        self.assertIn('@Table(name = "users")', content)
        self.assertIn('public class User {', content)
        self.assertIn('private Long id;', content)
        self.assertIn('private String username;', content)
        self.assertIn('public Long getId()', content)
        self.assertIn('public void setId(Long id)', content)
    
    def test_generate_attributes(self):
        """Test attribute generation."""
        attributes_content = self.generator.generate_attributes(self.sample_entity_data['attributes'])
        
        self.assertIn('@Id', attributes_content)
        self.assertIn('@GeneratedValue(strategy = GenerationType.IDENTITY)', attributes_content)
        self.assertIn('private Long id;', attributes_content)
        self.assertIn('@NotNull', attributes_content)
        self.assertIn('private String username;', attributes_content)
    
    def test_generate_relationships(self):
        """Test relationship generation."""
        relationships_content = self.generator.generate_relationships(self.sample_entity_data['relationships'])
        
        self.assertIn('@OneToMany(mappedBy = "user", cascade = CascadeType.ALL)', relationships_content)
        self.assertIn('private List<Order> orders;', relationships_content)
    
    def test_generate_constructors(self):
        """Test constructor generation."""
        constructors_content = self.generator.generate_constructors(self.sample_entity_data)
        
        self.assertIn('public User() {}', constructors_content)
        self.assertIn('public User(String username)', constructors_content)
        self.assertIn('this.username = username;', constructors_content)
    
    def test_generate_getters_setters(self):
        """Test getter and setter generation."""
        getters_setters = self.generator.generate_getters_setters(self.sample_entity_data['attributes'])
        
        self.assertIn('public Long getId()', getters_setters)
        self.assertIn('return id;', getters_setters)
        self.assertIn('public void setId(Long id)', getters_setters)
        self.assertIn('this.id = id;', getters_setters)
    
    @patch('builtins.open', new_callable=mock_open)
    def test_write_entity_file(self, mock_file):
        """Test entity file writing."""
        output_dir = '/tmp/entities'
        
        self.generator.write_entity_file(self.sample_entity_data, output_dir)
        
        expected_path = os.path.join(output_dir, 'User.java')
        mock_file.assert_called_once_with(expected_path, 'w', encoding='utf-8')
    
    def test_get_file_statistics(self):
        """Test file statistics generation."""
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=1024):
            
            stats = self.generator.get_file_statistics('/tmp/entities/User.java')
            
            self.assertEqual(stats['file_size'], 1024)
            self.assertTrue(stats['exists'])


class SpringBootRepositoryGeneratorTestCase(TestCase):
    """Test cases for SpringBootRepositoryGenerator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.generator = SpringBootRepositoryGenerator()
        self.sample_repository_data = {
            'class_name': 'UserRepository',
            'entity_name': 'User',
            'entity_id_type': 'Long',
            'package': 'com.example.repository',
            'custom_methods': [
                {
                    'name': 'findByUsername',
                    'return_type': 'Optional<User>',
                    'parameters': [{'name': 'username', 'type': 'String'}]
                },
                {
                    'name': 'findByEmailAndIsActive',
                    'return_type': 'List<User>',
                    'parameters': [
                        {'name': 'email', 'type': 'String'},
                        {'name': 'isActive', 'type': 'Boolean'}
                    ]
                }
            ],
            'query_methods': [
                {
                    'name': 'countActiveUsers',
                    'query': 'SELECT COUNT(u) FROM User u WHERE u.isActive = true',
                    'return_type': 'Long'
                }
            ]
        }
    
    def test_generate_repository_content(self):
        """Test repository content generation."""
        content = self.generator.generate_repository_content(self.sample_repository_data)
        
        self.assertIn('package com.example.repository;', content)
        self.assertIn('import org.springframework.data.jpa.repository.JpaRepository;', content)
        self.assertIn('public interface UserRepository extends JpaRepository<User, Long>', content)
        self.assertIn('Optional<User> findByUsername(String username);', content)
        self.assertIn('List<User> findByEmailAndIsActive(String email, Boolean isActive);', content)
    
    def test_generate_custom_methods(self):
        """Test custom method generation."""
        methods_content = self.generator.generate_custom_methods(self.sample_repository_data['custom_methods'])
        
        self.assertIn('Optional<User> findByUsername(String username);', methods_content)
        self.assertIn('List<User> findByEmailAndIsActive(String email, Boolean isActive);', methods_content)
    
    def test_generate_query_methods(self):
        """Test query method generation."""
        query_methods = self.generator.generate_query_methods(self.sample_repository_data['query_methods'])
        
        self.assertIn('@Query("SELECT COUNT(u) FROM User u WHERE u.isActive = true")', query_methods)
        self.assertIn('Long countActiveUsers();', query_methods)
    
    def test_generate_imports(self):
        """Test import generation."""
        imports = self.generator.generate_imports(self.sample_repository_data)
        
        expected_imports = [
            'org.springframework.data.jpa.repository.JpaRepository',
            'org.springframework.data.jpa.repository.Query',
            'java.util.Optional',
            'java.util.List'
        ]
        
        for expected_import in expected_imports:
            self.assertIn(expected_import, imports)


class SpringBootServiceGeneratorTestCase(TestCase):
    """Test cases for SpringBootServiceGenerator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.generator = SpringBootServiceGenerator()
        self.sample_service_data = {
            'class_name': 'UserService',
            'entity_name': 'User',
            'repository_name': 'UserRepository',
            'package': 'com.example.service',
            'crud_methods': [
                {'name': 'findAll', 'return_type': 'List<User>'},
                {'name': 'findById', 'return_type': 'Optional<User>', 'parameters': [{'name': 'id', 'type': 'Long'}]},
                {'name': 'save', 'return_type': 'User', 'parameters': [{'name': 'user', 'type': 'User'}]},
                {'name': 'deleteById', 'return_type': 'void', 'parameters': [{'name': 'id', 'type': 'Long'}]}
            ],
            'custom_methods': [
                {
                    'name': 'findByUsername',
                    'return_type': 'Optional<User>',
                    'parameters': [{'name': 'username', 'type': 'String'}],
                    'implementation': 'return userRepository.findByUsername(username);'
                }
            ]
        }
    
    def test_generate_service_content(self):
        """Test service content generation."""
        content = self.generator.generate_service_content(self.sample_service_data)
        
        self.assertIn('package com.example.service;', content)
        self.assertIn('@Service', content)
        self.assertIn('public class UserService {', content)
        self.assertIn('@Autowired', content)
        self.assertIn('private UserRepository userRepository;', content)
        self.assertIn('public List<User> findAll()', content)
        self.assertIn('public Optional<User> findById(Long id)', content)
    
    def test_generate_crud_methods(self):
        """Test CRUD method generation."""
        crud_content = self.generator.generate_crud_methods(self.sample_service_data)
        
        self.assertIn('public List<User> findAll() {', crud_content)
        self.assertIn('return userRepository.findAll();', crud_content)
        self.assertIn('public User save(User user) {', crud_content)
        self.assertIn('return userRepository.save(user);', crud_content)
        self.assertIn('public void deleteById(Long id) {', crud_content)
        self.assertIn('userRepository.deleteById(id);', crud_content)
    
    def test_generate_custom_methods(self):
        """Test custom method generation."""
        custom_content = self.generator.generate_custom_methods(self.sample_service_data['custom_methods'])
        
        self.assertIn('public Optional<User> findByUsername(String username) {', custom_content)
        self.assertIn('return userRepository.findByUsername(username);', custom_content)
    
    def test_generate_validation_methods(self):
        """Test validation method generation."""
        validation_methods = self.generator.generate_validation_methods(self.sample_service_data)
        
        self.assertIn('private void validateUser(User user)', validation_methods)
        self.assertIn('if (user == null)', validation_methods)
        self.assertIn('throw new IllegalArgumentException', validation_methods)


class SpringBootControllerGeneratorTestCase(TestCase):
    """Test cases for SpringBootControllerGenerator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.generator = SpringBootControllerGenerator()
        self.sample_controller_data = {
            'class_name': 'UserController',
            'entity_name': 'User',
            'service_name': 'UserService',
            'base_path': '/api/users',
            'package': 'com.example.controller',
            'endpoints': [
                {
                    'method': 'GET',
                    'path': '',
                    'handler': 'getAllUsers',
                    'return_type': 'ResponseEntity<List<User>>'
                },
                {
                    'method': 'GET',
                    'path': '/{id}',
                    'handler': 'getUserById',
                    'return_type': 'ResponseEntity<User>',
                    'parameters': [{'name': 'id', 'type': 'Long', 'annotation': '@PathVariable'}]
                },
                {
                    'method': 'POST',
                    'path': '',
                    'handler': 'createUser',
                    'return_type': 'ResponseEntity<User>',
                    'parameters': [{'name': 'user', 'type': 'User', 'annotation': '@RequestBody @Valid'}]
                }
            ]
        }
    
    def test_generate_controller_content(self):
        """Test controller content generation."""
        content = self.generator.generate_controller_content(self.sample_controller_data)
        
        self.assertIn('package com.example.controller;', content)
        self.assertIn('@RestController', content)
        self.assertIn('@RequestMapping("/api/users")', content)
        self.assertIn('public class UserController {', content)
        self.assertIn('@Autowired', content)
        self.assertIn('private UserService userService;', content)
    
    def test_generate_endpoints(self):
        """Test endpoint generation."""
        endpoints_content = self.generator.generate_endpoints(self.sample_controller_data['endpoints'])
        
        self.assertIn('@GetMapping', endpoints_content)
        self.assertIn('public ResponseEntity<List<User>> getAllUsers()', endpoints_content)
        self.assertIn('@GetMapping("/{id}")', endpoints_content)
        self.assertIn('@PathVariable Long id', endpoints_content)
        self.assertIn('@PostMapping', endpoints_content)
        self.assertIn('@RequestBody @Valid User user', endpoints_content)
    
    def test_generate_exception_handlers(self):
        """Test exception handler generation."""
        exception_handlers = self.generator.generate_exception_handlers()
        
        self.assertIn('@ExceptionHandler', exception_handlers)
        self.assertIn('handleEntityNotFoundException', exception_handlers)
        self.assertIn('handleValidationException', exception_handlers)
        self.assertIn('ResponseEntity.notFound()', exception_handlers)
    
    def test_generate_openapi_annotations(self):
        """Test OpenAPI annotation generation."""
        endpoint = self.sample_controller_data['endpoints'][1]  # GET /{id}
        annotations = self.generator.generate_openapi_annotations(endpoint)
        
        self.assertIn('@Operation', annotations)
        self.assertIn('@ApiResponse', annotations)
        self.assertIn('@Parameter', annotations)


class SpringBootGeneratorIntegrationTestCase(TestCase):
    """Integration tests for all SpringBoot generators."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.entity_generator = SpringBootEntityGenerator()
        self.repository_generator = SpringBootRepositoryGenerator()
        self.service_generator = SpringBootServiceGenerator()
        self.controller_generator = SpringBootControllerGenerator()
        
        self.sample_metadata = {
            'entities': [{
                'class_name': 'User',
                'table_name': 'users',
                'package': 'com.example.entity',
                'attributes': [
                    {
                        'name': 'id',
                        'java_type': 'Long',
                        'annotations': ['@Id', '@GeneratedValue(strategy = GenerationType.IDENTITY)']
                    }
                ],
                'relationships': [],
                'imports': ['javax.persistence.*'],
                'annotations': ['@Entity', '@Table(name = "users")']
            }],
            'repositories': [{
                'class_name': 'UserRepository',
                'entity_name': 'User',
                'entity_id_type': 'Long',
                'package': 'com.example.repository',
                'custom_methods': [],
                'query_methods': []
            }],
            'services': [{
                'class_name': 'UserService',
                'entity_name': 'User',
                'repository_name': 'UserRepository',
                'package': 'com.example.service',
                'crud_methods': [
                    {'name': 'findAll', 'return_type': 'List<User>'}
                ],
                'custom_methods': []
            }],
            'controllers': [{
                'class_name': 'UserController',
                'entity_name': 'User',
                'service_name': 'UserService',
                'base_path': '/api/users',
                'package': 'com.example.controller',
                'endpoints': [
                    {
                        'method': 'GET',
                        'path': '',
                        'handler': 'getAllUsers',
                        'return_type': 'ResponseEntity<List<User>>'
                    }
                ]
            }]
        }
    
    def test_generate_all_layers(self):
        """Test generating all SpringBoot layers."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Generate entity
            entity_content = self.entity_generator.generate_entity_content(self.sample_metadata['entities'][0])
            self.assertIn('public class User', entity_content)
            
            # Generate repository
            repository_content = self.repository_generator.generate_repository_content(self.sample_metadata['repositories'][0])
            self.assertIn('interface UserRepository', repository_content)
            
            # Generate service
            service_content = self.service_generator.generate_service_content(self.sample_metadata['services'][0])
            self.assertIn('class UserService', service_content)
            
            # Generate controller
            controller_content = self.controller_generator.generate_controller_content(self.sample_metadata['controllers'][0])
            self.assertIn('class UserController', controller_content)
    
    def test_cross_layer_consistency(self):
        """Test consistency across all generated layers."""
        entity_data = self.sample_metadata['entities'][0]
        repository_data = self.sample_metadata['repositories'][0]
        service_data = self.sample_metadata['services'][0]
        controller_data = self.sample_metadata['controllers'][0]
        
        # Check naming consistency
        self.assertEqual(entity_data['class_name'], 'User')
        self.assertEqual(repository_data['entity_name'], 'User')
        self.assertEqual(service_data['entity_name'], 'User')
        self.assertEqual(controller_data['entity_name'], 'User')
        
        # Check package structure consistency
        self.assertTrue(entity_data['package'].endswith('.entity'))
        self.assertTrue(repository_data['package'].endswith('.repository'))
        self.assertTrue(service_data['package'].endswith('.service'))
        self.assertTrue(controller_data['package'].endswith('.controller'))
    
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_file_generation_workflow(self, mock_file, mock_makedirs):
        """Test complete file generation workflow."""
        output_dir = '/tmp/springboot'
        
        # Generate all files
        for entity in self.sample_metadata['entities']:
            self.entity_generator.write_entity_file(entity, os.path.join(output_dir, 'entity'))
        
        for repository in self.sample_metadata['repositories']:
            self.repository_generator.write_repository_file(repository, os.path.join(output_dir, 'repository'))
        
        for service in self.sample_metadata['services']:
            self.service_generator.write_service_file(service, os.path.join(output_dir, 'service'))
        
        for controller in self.sample_metadata['controllers']:
            self.controller_generator.write_controller_file(controller, os.path.join(output_dir, 'controller'))
        
        # Verify directory creation
        expected_dirs = [
            os.path.join(output_dir, 'entity'),
            os.path.join(output_dir, 'repository'),
            os.path.join(output_dir, 'service'),
            os.path.join(output_dir, 'controller')
        ]
        
        for expected_dir in expected_dirs:
            mock_makedirs.assert_any_call(expected_dir, exist_ok=True)
        
        # Verify file creation
        expected_files = [
            'User.java',
            'UserRepository.java',
            'UserService.java',
            'UserController.java'
        ]
        
        self.assertEqual(mock_file.call_count, len(expected_files))


if __name__ == '__main__':
    unittest.main()
