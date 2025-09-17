"""
GenerationTemplate model for SpringBoot code generation template definitions.
"""

from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class GenerationTemplate(models.Model):
    """
    SpringBoot code generation templates with Jinja2 template definitions.
    """
    
    class TemplateType(models.TextChoices):
        ENTITY = 'ENTITY', 'JPA Entity'
        REPOSITORY = 'REPOSITORY', 'Repository Interface'
        SERVICE = 'SERVICE', 'Service Class'
        CONTROLLER = 'CONTROLLER', 'REST Controller'
        DTO = 'DTO', 'Data Transfer Object'
        CONFIG = 'CONFIG', 'Configuration Class'
        TEST = 'TEST', 'Test Class'
        POM_XML = 'POM_XML', 'Maven POM'
        APPLICATION_PROPERTIES = 'APPLICATION_PROPERTIES', 'Application Properties'
        MAIN_CLASS = 'MAIN_CLASS', 'Main Application Class'
    
    class TemplateFramework(models.TextChoices):
        SPRING_BOOT_2 = 'SPRING_BOOT_2', 'Spring Boot 2.x'
        SPRING_BOOT_3 = 'SPRING_BOOT_3', 'Spring Boot 3.x'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField()
    template_type = models.CharField(
        max_length=25,
        choices=TemplateType.choices
    )
    framework_version = models.CharField(
        max_length=20,
        choices=TemplateFramework.choices,
        default=TemplateFramework.SPRING_BOOT_3
    )
    template_content = models.TextField(
        help_text="Jinja2 template content"
    )
    default_variables = models.JSONField(
        default=dict,
        help_text="Default template variables and their values"
    )
    required_variables = models.JSONField(
        default=list,
        help_text="Required variables that must be provided"
    )
    output_filename_pattern = models.CharField(
        max_length=255,
        help_text="Pattern for generated file names (supports template variables)"
    )
    output_directory = models.CharField(
        max_length=255,
        help_text="Target directory for generated files"
    )
    file_extension = models.CharField(
        max_length=10,
        default='.java'
    )
    is_system_template = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    version = models.CharField(max_length=20, default='1.0')
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_generation_templates'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'generation_templates'
        ordering = ['template_type', 'name']
        indexes = [
            models.Index(fields=['template_type', 'framework_version']),
            models.Index(fields=['is_system_template', 'is_active']),
            models.Index(fields=['created_by', 'created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'template_type', 'framework_version'],
                name='unique_template_per_type_framework'
            )
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"
    
    def render_template(self, context: dict) -> str:
        """Render template with provided context variables."""
        from jinja2 import Template
        
        try:
            # Merge default variables with provided context
            merged_context = {**self.default_variables, **context}
            
            # Create Jinja2 template
            template = Template(self.template_content)
            
            # Render with context
            rendered_content = template.render(**merged_context)
            
            return rendered_content
            
        except Exception as e:
            raise ValueError(f"Template rendering failed: {str(e)}")
    
    def generate_filename(self, context: dict) -> str:
        """Generate output filename using pattern and context."""
        from jinja2 import Template
        
        try:
            filename_template = Template(self.output_filename_pattern)
            filename = filename_template.render(**context)
            
            if not filename.endswith(self.file_extension):
                filename += self.file_extension
                
            return filename
            
        except Exception as e:
            return f"Generated{self.file_extension}"
    
    def validate_template(self) -> dict:
        """Validate template syntax and structure."""
        from jinja2 import Template, TemplateSyntaxError
        
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': []
        }
        
        try:
            # Test template syntax
            Template(self.template_content)
            
            # Test filename pattern
            Template(self.output_filename_pattern)
            
        except TemplateSyntaxError as e:
            validation_result['is_valid'] = False
            validation_result['errors'].append(f"Template syntax error: {str(e)}")
        
        # Check required variables
        if not self.required_variables:
            validation_result['warnings'].append("No required variables defined")
        
        return validation_result
    
    @classmethod
    def get_system_templates(cls) -> dict:
        """Get predefined system templates for SpringBoot generation."""
        return {
            'entity': {
                'name': 'SpringBoot JPA Entity',
                'description': 'Standard JPA Entity class template',
                'template_type': 'ENTITY',
                'template_content': '''package {{ package_name }};

{% for import in imports %}
import {{ import }};
{% endfor %}

/**
 * {{ class_name }} entity class.
 * Generated from UML diagram.
 */
@Entity
{% if table_name != class_name.lower() %}
@Table(name = "{{ table_name }}")
{% endif %}
public class {{ class_name }} {

{% for attribute in attributes %}
    {% if attribute.annotations %}
    {% for annotation in attribute.annotations %}
    {{ annotation }}
    {% endfor %}
    {% endif %}
    private {{ attribute.type }} {{ attribute.name }};

{% endfor %}
    // Constructors
    public {{ class_name }}() {}

{% if attributes|length > 1 %}
    public {{ class_name }}({% for attr in attributes if attr.name != 'id' %}{{ attr.type }} {{ attr.name }}{% if not loop.last %}, {% endif %}{% endfor %}) {
{% for attr in attributes if attr.name != 'id' %}
        this.{{ attr.name }} = {{ attr.name }};
{% endfor %}
    }
{% endif %}

    // Getters and Setters
{% for attribute in attributes %}
    public {{ attribute.type }} get{{ attribute.name|title }}() {
        return {{ attribute.name }};
    }

    public void set{{ attribute.name|title }}({{ attribute.type }} {{ attribute.name }}) {
        this.{{ attribute.name }} = {{ attribute.name }};
    }

{% endfor %}
    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof {{ class_name }})) return false;
        {{ class_name }} that = ({{ class_name }}) o;
        return Objects.equals(id, that.id);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id);
    }

    @Override
    public String toString() {
        return "{{ class_name }}{" +
{% for attr in attributes %}
                "{{ attr.name }}=" + {{ attr.name }} +
{% if not loop.last %}
                ", " +
{% endif %}
{% endfor %}
                '}';
    }
}''',
                'default_variables': {
                    'package_name': 'com.enterprise.generated.entities',
                    'imports': [
                        'javax.persistence.*',
                        'java.util.Objects',
                        'org.hibernate.annotations.CreationTimestamp',
                        'org.hibernate.annotations.UpdateTimestamp',
                        'java.time.LocalDateTime'
                    ]
                },
                'required_variables': ['class_name', 'attributes'],
                'output_filename_pattern': '{{ class_name }}.java',
                'output_directory': 'src/main/java/{{ package_name|replace(".", "/") }}'
            },
            'repository': {
                'name': 'SpringBoot JPA Repository',
                'description': 'JPA Repository interface template',
                'template_type': 'REPOSITORY',
                'template_content': '''package {{ package_name }};

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import {{ entity_package }}.{{ entity_name }};

import java.util.List;
import java.util.Optional;

/**
 * Repository interface for {{ entity_name }} entity.
 * Generated from UML diagram.
 */
@Repository
public interface {{ repository_name }} extends JpaRepository<{{ entity_name }}, {{ id_type }}> {

{% for method in custom_methods %}
    /**
     * {{ method.description }}
     */
    {% if method.query %}
    @Query("{{ method.query }}")
    {% endif %}
    {{ method.return_type }} {{ method.name }}({% for param in method.parameters %}@Param("{{ param.name }}") {{ param.type }} {{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %});

{% endfor %}
{% if searchable_fields %}
    // Dynamic search methods
{% for field in searchable_fields %}
    List<{{ entity_name }}> findBy{{ field.name|title }}({{ field.type }} {{ field.name }});
    List<{{ entity_name }}> findBy{{ field.name|title }}ContainingIgnoreCase({{ field.type }} {{ field.name }});
{% endfor %}
{% endif %}
}''',
                'default_variables': {
                    'package_name': 'com.enterprise.generated.repositories',
                    'entity_package': 'com.enterprise.generated.entities',
                    'id_type': 'Long',
                    'custom_methods': [],
                    'searchable_fields': []
                },
                'required_variables': ['repository_name', 'entity_name'],
                'output_filename_pattern': '{{ repository_name }}.java',
                'output_directory': 'src/main/java/{{ package_name|replace(".", "/") }}'
            },
            'service': {
                'name': 'SpringBoot Service Class',
                'description': 'Service layer class template',
                'template_type': 'SERVICE',
                'template_content': '''package {{ package_name }};

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import {{ entity_package }}.{{ entity_name }};
import {{ repository_package }}.{{ repository_name }};

import java.util.List;
import java.util.Optional;

/**
 * Service class for {{ entity_name }} business logic.
 * Generated from UML diagram.
 */
@Service
@Transactional
public class {{ service_name }} {

    @Autowired
    private {{ repository_name }} {{ repository_name|lower }};

    /**
     * Create new {{ entity_name }}.
     */
    public {{ entity_name }} create({{ entity_name }} {{ entity_name|lower }}) {
        return {{ repository_name|lower }}.save({{ entity_name|lower }});
    }

    /**
     * Get {{ entity_name }} by ID.
     */
    @Transactional(readOnly = true)
    public Optional<{{ entity_name }}> findById({{ id_type }} id) {
        return {{ repository_name|lower }}.findById(id);
    }

    /**
     * Get all {{ entity_name }} entities.
     */
    @Transactional(readOnly = true)
    public List<{{ entity_name }}> findAll() {
        return {{ repository_name|lower }}.findAll();
    }

    /**
     * Update {{ entity_name }}.
     */
    public {{ entity_name }} update({{ entity_name }} {{ entity_name|lower }}) {
        return {{ repository_name|lower }}.save({{ entity_name|lower }});
    }

    /**
     * Delete {{ entity_name }} by ID.
     */
    public void deleteById({{ id_type }} id) {
        {{ repository_name|lower }}.deleteById(id);
    }

    /**
     * Check if {{ entity_name }} exists by ID.
     */
    @Transactional(readOnly = true)
    public boolean existsById({{ id_type }} id) {
        return {{ repository_name|lower }}.existsById(id);
    }

{% for method in business_methods %}
    /**
     * {{ method.description }}
     */
    {% if method.readonly %}@Transactional(readOnly = true){% endif %}
    public {{ method.return_type }} {{ method.name }}({% for param in method.parameters %}{{ param.type }} {{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %}) {
        {{ method.implementation|default('// TODO: Implement business logic') }}
    }

{% endfor %}
}''',
                'default_variables': {
                    'package_name': 'com.enterprise.generated.services',
                    'entity_package': 'com.enterprise.generated.entities',
                    'repository_package': 'com.enterprise.generated.repositories',
                    'id_type': 'Long',
                    'business_methods': []
                },
                'required_variables': ['service_name', 'entity_name', 'repository_name'],
                'output_filename_pattern': '{{ service_name }}.java',
                'output_directory': 'src/main/java/{{ package_name|replace(".", "/") }}'
            },
            'controller': {
                'name': 'SpringBoot REST Controller',
                'description': 'REST API controller template',
                'template_type': 'CONTROLLER',
                'template_content': '''package {{ package_name }};

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.validation.annotation.Validated;
import javax.validation.Valid;
import java.util.List;
import java.util.Optional;

import {{ entity_package }}.{{ entity_name }};
import {{ service_package }}.{{ service_name }};

/**
 * REST Controller for {{ entity_name }} API endpoints.
 * Generated from UML diagram.
 */
@RestController
@RequestMapping("/api/{{ api_path }}")
@Validated
@CrossOrigin(origins = "*")
public class {{ controller_name }} {

    @Autowired
    private {{ service_name }} {{ service_name|lower }};

    /**
     * Create new {{ entity_name }}.
     */
    @PostMapping
    public ResponseEntity<{{ entity_name }}> create(@Valid @RequestBody {{ entity_name }} {{ entity_name|lower }}) {
        {{ entity_name }} created = {{ service_name|lower }}.create({{ entity_name|lower }});
        return ResponseEntity.ok(created);
    }

    /**
     * Get {{ entity_name }} by ID.
     */
    @GetMapping("/{id}")
    public ResponseEntity<{{ entity_name }}> findById(@PathVariable {{ id_type }} id) {
        Optional<{{ entity_name }}> {{ entity_name|lower }} = {{ service_name|lower }}.findById(id);
        return {{ entity_name|lower }}.map(ResponseEntity::ok).orElse(ResponseEntity.notFound().build());
    }

    /**
     * Get all {{ entity_name }} entities.
     */
    @GetMapping
    public ResponseEntity<List<{{ entity_name }}>> findAll() {
        List<{{ entity_name }}> entities = {{ service_name|lower }}.findAll();
        return ResponseEntity.ok(entities);
    }

    /**
     * Update {{ entity_name }}.
     */
    @PutMapping("/{id}")
    public ResponseEntity<{{ entity_name }}> update(@PathVariable {{ id_type }} id, @Valid @RequestBody {{ entity_name }} {{ entity_name|lower }}) {
        if (!{{ service_name|lower }}.existsById(id)) {
            return ResponseEntity.notFound().build();
        }
        {{ entity_name|lower }}.setId(id);
        {{ entity_name }} updated = {{ service_name|lower }}.update({{ entity_name|lower }});
        return ResponseEntity.ok(updated);
    }

    /**
     * Delete {{ entity_name }} by ID.
     */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteById(@PathVariable {{ id_type }} id) {
        if (!{{ service_name|lower }}.existsById(id)) {
            return ResponseEntity.notFound().build();
        }
        {{ service_name|lower }}.deleteById(id);
        return ResponseEntity.noContent().build();
    }

{% for endpoint in custom_endpoints %}
    /**
     * {{ endpoint.description }}
     */
    @{{ endpoint.method }}("{{ endpoint.path }}")
    public ResponseEntity<{{ endpoint.return_type }}> {{ endpoint.name }}({% for param in endpoint.parameters %}{{ param.annotation }} {{ param.type }} {{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %}) {
        {{ endpoint.implementation|default('// TODO: Implement endpoint logic') }}
        return ResponseEntity.ok().build();
    }

{% endfor %}
}''',
                'default_variables': {
                    'package_name': 'com.enterprise.generated.controllers',
                    'entity_package': 'com.enterprise.generated.entities',
                    'service_package': 'com.enterprise.generated.services',
                    'id_type': 'Long',
                    'custom_endpoints': []
                },
                'required_variables': ['controller_name', 'entity_name', 'service_name', 'api_path'],
                'output_filename_pattern': '{{ controller_name }}.java',
                'output_directory': 'src/main/java/{{ package_name|replace(".", "/") }}'
            }
        }
    
    @classmethod
    def initialize_system_templates(cls, user: User) -> None:
        """Initialize predefined system templates."""
        system_templates = cls.get_system_templates()
        
        for template_key, template_data in system_templates.items():
            cls.objects.get_or_create(
                name=template_data['name'],
                template_type=template_data['template_type'],
                defaults={
                    'description': template_data['description'],
                    'template_content': template_data['template_content'],
                    'default_variables': template_data['default_variables'],
                    'required_variables': template_data['required_variables'],
                    'output_filename_pattern': template_data['output_filename_pattern'],
                    'output_directory': template_data['output_directory'],
                    'is_system_template': True,
                    'created_by': user
                }
            )
