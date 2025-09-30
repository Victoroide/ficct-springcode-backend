"""
Main orchestration service for SpringBoot code generation from UML diagrams.
"""

import os
import uuid
import tempfile
from typing import Dict, List, Optional
from django.utils import timezone
from django.conf import settings
from ..models import GenerationRequest, GeneratedProject, GenerationHistory
from .uml_parser_service import UMLParserService
from .springboot_entity_generator import SpringBootEntityGenerator
from .springboot_repository_generator import SpringBootRepositoryGenerator
from .springboot_service_generator import SpringBootServiceGenerator
from .springboot_controller_generator import SpringBootControllerGenerator
from .template_rendering_service import TemplateRenderingService
from .project_packaging_service import ProjectPackagingService


class CodeGeneratorService:
    """
    Main orchestration service for SpringBoot code generation.
    
    Coordinates the entire code generation process from UML diagram analysis
    to complete SpringBoot project creation and packaging.
    """
    
    def __init__(self):
        self.uml_parser = UMLParserService()
        self.entity_generator = SpringBootEntityGenerator()
        self.repository_generator = SpringBootRepositoryGenerator()
        self.service_generator = SpringBootServiceGenerator()
        self.controller_generator = SpringBootControllerGenerator()
        self.template_renderer = TemplateRenderingService()
        self.project_packager = ProjectPackagingService()
    
    def generate_springboot_project(self, generation_request: GenerationRequest) -> GeneratedProject:
        """
        Generate complete SpringBoot project from UML diagram.
        
        Args:
            generation_request: Generation configuration and parameters
            
        Returns:
            GeneratedProject instance with metadata and file paths
        """
        try:

            generation_request.start_generation()
            self._log_action(generation_request, 'GENERATION_STARTED', {
                'generation_type': generation_request.generation_type,
                'selected_classes_count': len(generation_request.get_selected_uml_classes())
            })

            workspace_path = self._create_workspace(generation_request)

            generation_request.update_progress(10, {'step': 'Parsing UML diagram'})
            uml_data = self.uml_parser.parse_diagram_structure(generation_request.diagram)

            generation_request.update_progress(20, {'step': 'Creating project structure'})
            project_structure = self._create_project_structure(workspace_path, generation_request)

            generated_files = []
            
            if generation_request.generation_type in ['FULL_PROJECT', 'ENTITIES_ONLY']:
                generation_request.update_progress(30, {'step': 'Generating JPA entities'})
                entity_files = self._generate_entities(workspace_path, uml_data, generation_request)
                generated_files.extend(entity_files)
            
            if generation_request.generation_type in ['FULL_PROJECT', 'REPOSITORIES_ONLY']:
                generation_request.update_progress(50, {'step': 'Generating repositories'})
                repo_files = self._generate_repositories(workspace_path, uml_data, generation_request)
                generated_files.extend(repo_files)
            
            if generation_request.generation_type in ['FULL_PROJECT', 'SERVICES_ONLY']:
                generation_request.update_progress(65, {'step': 'Generating services'})
                service_files = self._generate_services(workspace_path, uml_data, generation_request)
                generated_files.extend(service_files)
            
            if generation_request.generation_type in ['FULL_PROJECT', 'CONTROLLERS_ONLY']:
                generation_request.update_progress(80, {'step': 'Generating controllers'})
                controller_files = self._generate_controllers(workspace_path, uml_data, generation_request)
                generated_files.extend(controller_files)

            if generation_request.generation_type == 'FULL_PROJECT':
                generation_request.update_progress(90, {'step': 'Generating configuration'})
                config_files = self._generate_configuration_files(workspace_path, generation_request)
                generated_files.extend(config_files)

            generation_request.update_progress(95, {'step': 'Creating project package'})
            generated_project = self._create_generated_project(
                generation_request, workspace_path, generated_files
            )

            zip_path = generated_project.create_zip_archive()
            download_url = self._create_download_url(zip_path)

            generation_request.complete_generation(
                workspace_path, len(generated_files), download_url
            )
            
            self._log_action(generation_request, 'GENERATION_COMPLETED', {
                'files_generated': len(generated_files),
                'project_size': generated_project.zip_file_size,
                'generation_duration': generation_request.get_generation_duration()
            })
            
            return generated_project
            
        except Exception as e:

            error_details = {
                'error_message': str(e),
                'error_type': type(e).__name__,
                'generation_step': generation_request.progress_details.get('step', 'Unknown')
            }
            
            generation_request.fail_generation(error_details)
            
            self._log_action(generation_request, 'GENERATION_FAILED', error_details, success=False)
            
            raise Exception(f"Code generation failed: {str(e)}")
    
    def _create_workspace(self, generation_request: GenerationRequest) -> str:
        """Create temporary workspace for project generation."""
        workspace_id = str(uuid.uuid4())
        workspace_path = os.path.join(tempfile.gettempdir(), f"springboot_gen_{workspace_id}")
        os.makedirs(workspace_path, exist_ok=True)
        return workspace_path
    
    def _create_project_structure(self, workspace_path: str, 
                                generation_request: GenerationRequest) -> Dict:
        """Create basic SpringBoot project directory structure."""
        config = generation_request.get_springboot_config()

        package_path = config['group_id'].replace('.', '/')
        
        directories = [
            f"src/main/java/{package_path}/entities",
            f"src/main/java/{package_path}/repositories", 
            f"src/main/java/{package_path}/services",
            f"src/main/java/{package_path}/controllers",
            f"src/main/java/{package_path}/config",
            f"src/main/java/{package_path}/dto",
            "src/main/resources",
            f"src/test/java/{package_path}",
            "target"
        ]
        
        for directory in directories:
            os.makedirs(os.path.join(workspace_path, directory), exist_ok=True)
        
        return {
            'base_path': workspace_path,
            'package_path': package_path,
            'directories': directories
        }
    
    def _generate_entities(self, workspace_path: str, uml_data: Dict,
                          generation_request: GenerationRequest) -> List[Dict]:
        """Generate JPA entity classes."""
        return self.entity_generator.generate_entities(
            uml_data, workspace_path, generation_request.get_springboot_config()
        )
    
    def _generate_repositories(self, workspace_path: str, uml_data: Dict,
                             generation_request: GenerationRequest) -> List[Dict]:
        """Generate JPA repository interfaces."""
        return self.repository_generator.generate_repositories(
            uml_data, workspace_path, generation_request.get_springboot_config()
        )
    
    def _generate_services(self, workspace_path: str, uml_data: Dict,
                          generation_request: GenerationRequest) -> List[Dict]:
        """Generate service layer classes."""
        return self.service_generator.generate_services(
            uml_data, workspace_path, generation_request.get_springboot_config()
        )
    
    def _generate_controllers(self, workspace_path: str, uml_data: Dict,
                            generation_request: GenerationRequest) -> List[Dict]:
        """Generate REST controller classes."""
        return self.controller_generator.generate_controllers(
            uml_data, workspace_path, generation_request.get_springboot_config()
        )
    
    def _generate_configuration_files(self, workspace_path: str,
                                    generation_request: GenerationRequest) -> List[Dict]:
        """Generate configuration files (pom.xml, application.properties, etc)."""
        return self.project_packager.generate_configuration_files(
            workspace_path, generation_request.get_springboot_config()
        )
    
    def _create_generated_project(self, generation_request: GenerationRequest,
                                workspace_path: str, generated_files: List[Dict]) -> GeneratedProject:
        """Create GeneratedProject instance with metadata."""

        total_lines = sum(f.get('lines_of_code', 0) for f in generated_files)

        file_structure = {
            'tree': self._build_file_tree(generated_files),
            'files': generated_files
        }
        
        generated_project = GeneratedProject.objects.create(
            generation_request=generation_request,
            project=generation_request.project,
            diagram=generation_request.diagram,
            project_name=f"{generation_request.project.name}_generated",
            project_description=f"Generated SpringBoot project from {generation_request.diagram.name}",
            springboot_config=generation_request.get_springboot_config(),
            file_structure=file_structure,
            storage_path=workspace_path,
            total_files=len(generated_files),
            total_lines_of_code=total_lines,
            generated_by=generation_request.requested_by
        )
        
        return generated_project
    
    def _build_file_tree(self, generated_files: List[Dict]) -> Dict:
        """Build hierarchical file tree structure."""
        tree = {}
        
        for file_info in generated_files:
            path_parts = file_info['relative_path'].split('/')
            current_node = tree
            
            for part in path_parts[:-1]:  # Navigate to parent directory
                if part not in current_node:
                    current_node[part] = {}
                current_node = current_node[part]

            filename = path_parts[-1]
            current_node[filename] = {
                'type': 'file',
                'size': file_info.get('size', 0),
                'extension': file_info.get('extension', ''),
                'lines_of_code': file_info.get('lines_of_code', 0)
            }
        
        return tree
    
    def _create_download_url(self, zip_path: str) -> str:
        """Create temporary download URL for generated project."""

        filename = os.path.basename(zip_path)
        return f"/api/code-generation/download/{filename}"
    
    def _log_action(self, generation_request: GenerationRequest, action_type: str,
                   details: Dict, success: bool = True) -> None:
        """Log generation action to history."""
        GenerationHistory.log_action(
            generation_request=generation_request,
            action_type=action_type,
            user=generation_request.requested_by,
            details=details,
            success=success
        )
    
    def estimate_generation_complexity(self, diagram) -> Dict:
        """Estimate generation complexity and time requirements."""
        classes_count = len(diagram.get_classes())
        relationships_count = len(diagram.get_relationships())

        complexity_score = (classes_count * 2) + (relationships_count * 1)
        
        if complexity_score <= 10:
            complexity_level = 'Simple'
            estimated_time = 30  # seconds
        elif complexity_score <= 25:
            complexity_level = 'Medium'
            estimated_time = 60
        elif complexity_score <= 50:
            complexity_level = 'Complex'
            estimated_time = 120
        else:
            complexity_level = 'Very Complex'
            estimated_time = 300
        
        return {
            'complexity_score': complexity_score,
            'complexity_level': complexity_level,
            'estimated_time_seconds': estimated_time,
            'classes_count': classes_count,
            'relationships_count': relationships_count,
            'recommended_approach': self._get_complexity_recommendations(complexity_level)
        }
    
    def _get_complexity_recommendations(self, complexity_level: str) -> List[str]:
        """Get recommendations based on diagram complexity."""
        recommendations = {
            'Simple': [
                "Generate full project with all components",
                "Include comprehensive test coverage",
                "Add API documentation"
            ],
            'Medium': [
                "Consider generating components incrementally",
                "Review class relationships for optimization",
                "Add service layer abstractions"
            ],
            'Complex': [
                "Generate entities first, then other components",
                "Review domain model for proper separation",
                "Consider microservice architecture"
            ],
            'Very Complex': [
                "Break down into smaller diagrams",
                "Generate core entities first",
                "Consider domain-driven design patterns",
                "Implement in phases"
            ]
        }
        
        return recommendations.get(complexity_level, [])
