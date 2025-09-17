"""
Project Packaging Service for creating and managing SpringBoot project archives.
"""

import os
import shutil
import zipfile
import tempfile
from typing import Dict, List, Optional
from datetime import datetime
from .template_rendering_service import TemplateRenderingService


class ProjectPackagingService:
    """
    Service for packaging generated SpringBoot projects into downloadable archives.
    """
    
    def __init__(self):
        self.template_renderer = TemplateRenderingService()
        self.temp_dir = tempfile.gettempdir()
    
    def create_project_structure(self, config: Dict, uml_data: Dict) -> str:
        """
        Create complete SpringBoot project directory structure.
        
        Args:
            config: SpringBoot project configuration
            uml_data: Parsed UML diagram data
            
        Returns:
            Path to created project directory
        """
        project_name = config['artifact_id']
        project_path = os.path.join(self.temp_dir, f"{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        # Create base project structure
        self._create_maven_structure(project_path)
        
        # Create package directories
        package_path = config['group_id'].replace('.', '/')
        src_main_java = os.path.join(project_path, 'src', 'main', 'java', package_path)
        src_test_java = os.path.join(project_path, 'src', 'test', 'java', package_path)
        
        # Create package subdirectories
        for subdir in ['entities', 'repositories', 'services', 'controllers', 'dto', 'config']:
            os.makedirs(os.path.join(src_main_java, subdir), exist_ok=True)
            if subdir != 'config':  # No test for config
                os.makedirs(os.path.join(src_test_java, subdir), exist_ok=True)
        
        return project_path
    
    def generate_project_files(self, project_path: str, config: Dict, 
                             generated_files: List[Dict], uml_data: Dict) -> Dict:
        """
        Generate all project files and place them in the project structure.
        
        Args:
            project_path: Base project directory path
            config: SpringBoot project configuration
            generated_files: List of generated code files
            uml_data: Parsed UML diagram data
            
        Returns:
            Project generation summary
        """
        generation_summary = {
            'project_path': project_path,
            'files_generated': 0,
            'total_size': 0,
            'total_lines': 0,
            'file_breakdown': {
                'entities': 0,
                'repositories': 0,
                'services': 0,
                'controllers': 0,
                'dto': 0,
                'config': 0,
                'tests': 0
            }
        }
        
        # Copy generated code files
        for file_info in generated_files:
            self._copy_generated_file(project_path, file_info)
            generation_summary['files_generated'] += 1
            generation_summary['total_size'] += file_info.get('size', 0)
            generation_summary['total_lines'] += file_info.get('lines_of_code', 0)
            generation_summary['file_breakdown'][file_info['type']] += 1
        
        # Generate DTOs for all entities
        dto_files = self._generate_dto_files(project_path, config, uml_data)
        for dto_file in dto_files:
            generation_summary['files_generated'] += 1
            generation_summary['total_size'] += dto_file.get('size', 0)
            generation_summary['total_lines'] += dto_file.get('lines_of_code', 0)
            generation_summary['file_breakdown']['dto'] += 1
        
        # Generate configuration files
        config_files = self._generate_configuration_files(project_path, config, uml_data)
        for config_file in config_files:
            generation_summary['files_generated'] += 1
            generation_summary['total_size'] += config_file.get('size', 0)
            generation_summary['total_lines'] += config_file.get('lines_of_code', 0)
            generation_summary['file_breakdown']['config'] += 1
        
        # Generate main application class
        app_file = self._generate_main_application(project_path, config)
        generation_summary['files_generated'] += 1
        generation_summary['total_size'] += app_file.get('size', 0)
        generation_summary['total_lines'] += app_file.get('lines_of_code', 0)
        
        # Generate project metadata files
        metadata_files = self._generate_project_metadata(project_path, config, uml_data)
        generation_summary['files_generated'] += len(metadata_files)
        
        # Generate basic test files
        test_files = self._generate_test_files(project_path, config, uml_data)
        generation_summary['files_generated'] += len(test_files)
        generation_summary['file_breakdown']['tests'] = len(test_files)
        
        return generation_summary
    
    def create_project_archive(self, project_path: str, config: Dict) -> str:
        """
        Create ZIP archive of the complete project.
        
        Args:
            project_path: Path to project directory
            config: SpringBoot project configuration
            
        Returns:
            Path to created ZIP file
        """
        project_name = config['artifact_id']
        zip_filename = f"{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_path = os.path.join(self.temp_dir, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(project_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, project_path)
                    zipf.write(file_path, arcname)
        
        return zip_path
    
    def cleanup_project_files(self, project_path: str) -> None:
        """Clean up temporary project files."""
        if os.path.exists(project_path):
            shutil.rmtree(project_path)
    
    def get_project_statistics(self, project_path: str) -> Dict:
        """Get comprehensive project statistics."""
        stats = {
            'total_files': 0,
            'total_size': 0,
            'file_types': {},
            'directory_structure': {},
            'largest_files': []
        }
        
        for root, dirs, files in os.walk(project_path):
            for file in files:
                file_path = os.path.join(root, file)
                file_size = os.path.getsize(file_path)
                file_ext = os.path.splitext(file)[1]
                
                stats['total_files'] += 1
                stats['total_size'] += file_size
                
                if file_ext not in stats['file_types']:
                    stats['file_types'][file_ext] = {'count': 0, 'size': 0}
                
                stats['file_types'][file_ext]['count'] += 1
                stats['file_types'][file_ext]['size'] += file_size
                
                # Track largest files
                stats['largest_files'].append({
                    'name': file,
                    'path': os.path.relpath(file_path, project_path),
                    'size': file_size
                })
        
        # Sort largest files and keep top 10
        stats['largest_files'] = sorted(
            stats['largest_files'], 
            key=lambda x: x['size'], 
            reverse=True
        )[:10]
        
        return stats
    
    def _create_maven_structure(self, project_path: str) -> None:
        """Create standard Maven directory structure."""
        directories = [
            'src/main/java',
            'src/main/resources',
            'src/test/java',
            'src/test/resources'
        ]
        
        for directory in directories:
            os.makedirs(os.path.join(project_path, directory), exist_ok=True)
    
    def _copy_generated_file(self, project_path: str, file_info: Dict) -> None:
        """Copy generated file to appropriate location in project structure."""
        content = file_info['content']
        relative_path = file_info['relative_path']
        target_path = os.path.join(project_path, relative_path)
        
        # Ensure target directory exists
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        # Write file content
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _generate_dto_files(self, project_path: str, config: Dict, uml_data: Dict) -> List[Dict]:
        """Generate DTO classes for all entities."""
        dto_files = []
        package_path = config['group_id'].replace('.', '/') + '/dto'
        
        for class_data in uml_data['classes']:
            if class_data['springboot_mapping']['is_entity']:
                dto_context = self._build_dto_context(class_data, config)
                dto_content = self.template_renderer.render_dto_template(dto_context)
                
                dto_name = class_data['springboot_mapping']['dto_name']
                file_path = os.path.join(project_path, 'src/main/java', package_path, f"{dto_name}.java")
                
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(dto_content)
                
                dto_files.append({
                    'type': 'dto',
                    'name': dto_name,
                    'path': file_path,
                    'size': len(dto_content.encode('utf-8')),
                    'lines_of_code': len(dto_content.split('\n'))
                })
        
        return dto_files
    
    def _generate_configuration_files(self, project_path: str, config: Dict, uml_data: Dict) -> List[Dict]:
        """Generate configuration files (pom.xml, application.properties, etc.)."""
        config_files = []
        
        # Generate pom.xml
        pom_context = self._build_pom_context(config, uml_data)
        pom_content = self.template_renderer.render_pom_template(pom_context)
        pom_path = os.path.join(project_path, 'pom.xml')
        
        with open(pom_path, 'w', encoding='utf-8') as f:
            f.write(pom_content)
        
        config_files.append({
            'type': 'config',
            'name': 'pom.xml',
            'path': pom_path,
            'size': len(pom_content.encode('utf-8')),
            'lines_of_code': len(pom_content.split('\n'))
        })
        
        # Generate application.properties
        props_context = self._build_properties_context(config)
        props_content = self.template_renderer.render_application_properties_template(props_context)
        props_path = os.path.join(project_path, 'src/main/resources', 'application.properties')
        
        os.makedirs(os.path.dirname(props_path), exist_ok=True)
        with open(props_path, 'w', encoding='utf-8') as f:
            f.write(props_content)
        
        config_files.append({
            'type': 'config',
            'name': 'application.properties',
            'path': props_path,
            'size': len(props_content.encode('utf-8')),
            'lines_of_code': len(props_content.split('\n'))
        })
        
        return config_files
    
    def _generate_main_application(self, project_path: str, config: Dict) -> Dict:
        """Generate main Spring Boot application class."""
        app_context = {
            'package_name': config['group_id'],
            'application_name': config['application_class_name']
        }
        
        app_content = self.template_renderer.render_application_template(app_context)
        app_path = os.path.join(
            project_path, 
            'src/main/java', 
            config['group_id'].replace('.', '/'), 
            f"{config['application_class_name']}.java"
        )
        
        os.makedirs(os.path.dirname(app_path), exist_ok=True)
        with open(app_path, 'w', encoding='utf-8') as f:
            f.write(app_content)
        
        return {
            'type': 'application',
            'name': config['application_class_name'],
            'path': app_path,
            'size': len(app_content.encode('utf-8')),
            'lines_of_code': len(app_content.split('\n'))
        }
    
    def _generate_project_metadata(self, project_path: str, config: Dict, uml_data: Dict) -> List[Dict]:
        """Generate project metadata files (README, .gitignore, etc.)."""
        metadata_files = []
        
        # Generate README.md
        readme_context = self._build_readme_context(config, uml_data)
        readme_content = self.template_renderer.render_readme_template(readme_context)
        readme_path = os.path.join(project_path, 'README.md')
        
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        metadata_files.append({
            'type': 'metadata',
            'name': 'README.md',
            'path': readme_path
        })
        
        # Generate .gitignore
        gitignore_content = self._generate_gitignore_content()
        gitignore_path = os.path.join(project_path, '.gitignore')
        
        with open(gitignore_path, 'w', encoding='utf-8') as f:
            f.write(gitignore_content)
        
        metadata_files.append({
            'type': 'metadata',
            'name': '.gitignore',
            'path': gitignore_path
        })
        
        return metadata_files
    
    def _generate_test_files(self, project_path: str, config: Dict, uml_data: Dict) -> List[Dict]:
        """Generate basic test files for entities."""
        test_files = []
        package_path = config['group_id'].replace('.', '/')
        
        # Generate application test
        app_test_content = self._generate_application_test_content(config)
        app_test_path = os.path.join(
            project_path, 
            'src/test/java', 
            package_path, 
            f"{config['application_class_name']}Tests.java"
        )
        
        os.makedirs(os.path.dirname(app_test_path), exist_ok=True)
        with open(app_test_path, 'w', encoding='utf-8') as f:
            f.write(app_test_content)
        
        test_files.append({
            'type': 'test',
            'name': f"{config['application_class_name']}Tests.java",
            'path': app_test_path
        })
        
        return test_files
    
    def _build_dto_context(self, class_data: Dict, config: Dict) -> Dict:
        """Build context for DTO template."""
        dto_name = class_data['springboot_mapping']['dto_name']
        
        fields = []
        for attr in class_data['attributes']:
            field = {
                'name': attr['name'],
                'type': attr['java_type'],
                'annotations': self._get_dto_validation_annotations(attr)
            }
            fields.append(field)
        
        return {
            'dto_name': dto_name,
            'package_name': f"{config['group_id']}.dto",
            'imports': self._get_dto_imports(fields),
            'fields': fields
        }
    
    def _build_pom_context(self, config: Dict, uml_data: Dict) -> Dict:
        """Build context for pom.xml template."""
        dependencies = [
            {'group_id': 'org.springframework.boot', 'artifact_id': 'spring-boot-starter-web'},
            {'group_id': 'org.springframework.boot', 'artifact_id': 'spring-boot-starter-data-jpa'},
            {'group_id': 'org.springframework.boot', 'artifact_id': 'spring-boot-starter-validation'},
            {'group_id': 'com.h2database', 'artifact_id': 'h2', 'scope': 'runtime'},
            {'group_id': 'org.postgresql', 'artifact_id': 'postgresql', 'scope': 'runtime'},
            {'group_id': 'org.projectlombok', 'artifact_id': 'lombok', 'scope': 'provided'},
            {'group_id': 'org.springdoc', 'artifact_id': 'springdoc-openapi-starter-webmvc-ui'},
            {'group_id': 'org.springframework.boot', 'artifact_id': 'spring-boot-starter-test', 'scope': 'test'}
        ]
        
        return {
            'group_id': config['group_id'],
            'artifact_id': config['artifact_id'],
            'version': config.get('version', '1.0.0'),
            'project_name': config.get('project_name', config['artifact_id']),
            'description': config.get('description', 'Generated SpringBoot application'),
            'spring_boot_version': config.get('spring_boot_version', '3.2.0'),
            'java_version': config.get('java_version', '17'),
            'dependencies': dependencies
        }
    
    def _build_properties_context(self, config: Dict) -> Dict:
        """Build context for application.properties template."""
        return {
            'server_port': config.get('server_port', '8080'),
            'application_name': config['artifact_id'],
            'database_url': 'jdbc:h2:mem:testdb',
            'database_username': 'sa',
            'database_password': 'password',
            'database_driver': 'org.h2.Driver',
            'jpa_ddl_auto': 'create-drop',
            'jpa_show_sql': 'true',
            'jpa_dialect': 'org.hibernate.dialect.H2Dialect',
            'log_level_web': 'INFO',
            'log_level_sql': 'DEBUG',
            'log_level_sql_params': 'TRACE'
        }
    
    def _build_readme_context(self, config: Dict, uml_data: Dict) -> Dict:
        """Build context for README.md template."""
        entities = []
        for class_data in uml_data['classes']:
            if class_data['springboot_mapping']['is_entity']:
                entities.append({
                    'name': class_data['name'],
                    'description': class_data.get('documentation', f"{class_data['name']} entity")
                })
        
        return {
            'project_name': config.get('project_name', config['artifact_id']),
            'description': config.get('description', 'Generated SpringBoot application'),
            'artifact_id': config['artifact_id'],
            'java_version': config.get('java_version', '17'),
            'server_port': config.get('server_port', '8080'),
            'database_name': 'H2',
            'package_path': config['group_id'].replace('.', '/'),
            'application_name': config['application_class_name'],
            'entities': entities
        }
    
    def _get_dto_validation_annotations(self, attr: Dict) -> List[str]:
        """Get validation annotations for DTO field."""
        annotations = []
        
        if attr.get('is_final') or '@NotNull' in attr.get('annotations', []):
            annotations.append('@NotNull')
        
        if 'String' in attr['java_type'] and '@NotBlank' in attr.get('annotations', []):
            annotations.append('@NotBlank')
        
        return annotations
    
    def _get_dto_imports(self, fields: List[Dict]) -> List[str]:
        """Get imports needed for DTO class."""
        imports = ['java.util.Objects']
        
        has_validation = any(field.get('annotations') for field in fields)
        if has_validation:
            imports.append('javax.validation.constraints.*')
        
        return imports
    
    def _generate_gitignore_content(self) -> str:
        """Generate .gitignore content for SpringBoot project."""
        return """# Compiled class files
*.class

# Log files
*.log

# BlueJ files
*.ctxt

# Mobile Tools for Java (J2ME)
.mtj.tmp/

# Package Files
*.jar
*.war
*.nar
*.ear
*.zip
*.tar.gz
*.rar

# Virtual machine crash logs
hs_err_pid*

# Maven
target/
pom.xml.tag
pom.xml.versionsBackup
pom.xml.next
release.properties
dependency-reduced-pom.xml
buildNumber.properties
.mvn/timing.properties
.mvn/wrapper/maven-wrapper.jar

# Spring Boot
.gradle
build/
!gradle/wrapper/gradle-wrapper.jar
!**/src/main/**/build/
!**/src/test/**/build/

# STS
.apt_generated
.classpath
.factorypath
.project
.settings
.springBeans
.sts4-cache

# IntelliJ IDEA
.idea
*.iws
*.iml
*.ipr
out/
!**/src/main/**/out/
!**/src/test/**/out/

# NetBeans
/nbproject/private/
/nbbuild/
/dist/
/nbdist/
/.nb-gradle/

# VS Code
.vscode/

# Mac OS
.DS_Store

# Windows
Thumbs.db
ehthumbs.db
Desktop.ini

# Application specific
application-*.properties
!application.properties
!application-sample.properties"""
    
    def _generate_application_test_content(self, config: Dict) -> str:
        """Generate basic application test class."""
        return f"""package {config['group_id']};

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest
class {config['application_class_name']}Tests {{

    @Test
    void contextLoads() {{
        // Basic test to ensure Spring context loads successfully
    }}
}}"""
