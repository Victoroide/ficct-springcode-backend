"""
Template Rendering Service for SpringBoot code generation using Jinja2 templates.
"""

import os
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, Template, TemplateNotFound
from django.conf import settings


class TemplateRenderingService:
    """
    Service for rendering SpringBoot code templates using Jinja2.
    """
    
    def __init__(self):
        self.template_dir = os.path.join(settings.BASE_DIR, 'apps', 'templates', 'springboot')
        self.jinja_env = self._create_jinja_environment()
    
    def _create_jinja_environment(self) -> Environment:
        """Create and configure Jinja2 environment."""
        env = Environment(
            loader=FileSystemLoader(self.template_dir),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True
        )
        
        # Add custom filters
        env.filters['camel_case'] = self._to_camel_case
        env.filters['pascal_case'] = self._to_pascal_case
        env.filters['snake_case'] = self._to_snake_case
        env.filters['kebab_case'] = self._to_kebab_case
        env.filters['capitalize_first'] = self._capitalize_first
        env.filters['java_type'] = self._format_java_type
        
        return env
    
    def render_entity_template(self, context: Dict[str, Any]) -> str:
        """Render JPA Entity template."""
        return self._render_template('entity.java.j2', context)
    
    def render_repository_template(self, context: Dict[str, Any]) -> str:
        """Render JPA Repository template."""
        return self._render_template('repository.java.j2', context)
    
    def render_service_template(self, context: Dict[str, Any]) -> str:
        """Render Service class template."""
        return self._render_template('service.java.j2', context)
    
    def render_controller_template(self, context: Dict[str, Any]) -> str:
        """Render REST Controller template."""
        return self._render_template('controller.java.j2', context)
    
    def render_dto_template(self, context: Dict[str, Any]) -> str:
        """Render DTO class template."""
        return self._render_template('dto.java.j2', context)
    
    def render_application_template(self, context: Dict[str, Any]) -> str:
        """Render main Application class template."""
        return self._render_template('application.java.j2', context)
    
    def render_pom_template(self, context: Dict[str, Any]) -> str:
        """Render Maven pom.xml template."""
        return self._render_template('pom.xml.j2', context)
    
    def render_application_properties_template(self, context: Dict[str, Any]) -> str:
        """Render application.properties template."""
        return self._render_template('application.properties.j2', context)
    
    def render_application_yml_template(self, context: Dict[str, Any]) -> str:
        """Render application.yml template."""
        return self._render_template('application.yml.j2', context)
    
    def render_dockerfile_template(self, context: Dict[str, Any]) -> str:
        """Render Dockerfile template."""
        return self._render_template('Dockerfile.j2', context)
    
    def render_readme_template(self, context: Dict[str, Any]) -> str:
        """Render README.md template."""
        return self._render_template('README.md.j2', context)
    
    def render_gitignore_template(self, context: Dict[str, Any]) -> str:
        """Render .gitignore template."""
        return self._render_template('gitignore.j2', context)
    
    def render_test_template(self, context: Dict[str, Any]) -> str:
        """Render test class template."""
        return self._render_template('test.java.j2', context)
    
    def render_custom_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render custom template by name."""
        return self._render_template(template_name, context)
    
    def _render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render template with given context."""
        try:
            template = self.jinja_env.get_template(template_name)
            return template.render(**context)
        except TemplateNotFound:
            # Fallback to inline template if file not found
            return self._get_inline_template(template_name, context)
        except Exception as e:
            raise Exception(f"Error rendering template {template_name}: {str(e)}")
    
    def _get_inline_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Generate inline template if template file not found."""
        
        if template_name == 'entity.java.j2':
            return self._generate_entity_inline_template(context)
        elif template_name == 'repository.java.j2':
            return self._generate_repository_inline_template(context)
        elif template_name == 'service.java.j2':
            return self._generate_service_inline_template(context)
        elif template_name == 'controller.java.j2':
            return self._generate_controller_inline_template(context)
        elif template_name == 'dto.java.j2':
            return self._generate_dto_inline_template(context)
        elif template_name == 'application.java.j2':
            return self._generate_application_inline_template(context)
        elif template_name == 'pom.xml.j2':
            return self._generate_pom_inline_template(context)
        elif template_name == 'application.properties.j2':
            return self._generate_properties_inline_template(context)
        elif template_name == 'README.md.j2':
            return self._generate_readme_inline_template(context)
        else:
            raise TemplateNotFound(f"Template {template_name} not found and no inline fallback available")
    
    def _generate_entity_inline_template(self, context: Dict[str, Any]) -> str:
        """Generate inline JPA Entity template."""
        template_str = '''package {{ package_name }};

{% for import in imports %}
import {{ import }};
{% endfor %}

{% for annotation in class_annotations %}
{{ annotation }}
{% endfor %}
public class {{ class_name }} {

{% for attr in attributes %}
    {% for annotation in attr.annotations %}
    {{ annotation }}
    {% endfor %}
    private {{ attr.type }} {{ attr.name }};
{% endfor %}

{% for rel in relationships %}
    {% if rel.jpa_annotation %}
    {{ rel.jpa_annotation }}{% if rel.fetch_type %}(fetch = FetchType.{{ rel.fetch_type }}{% if rel.cascade_types %}, cascade = {{% for cascade in rel.cascade_types %}{{ cascade }}{% if not loop.last %}, {% endif %}{% endfor %}}{% endif %}){% endif %}
    {% if rel.join_column %}
    @JoinColumn(name = "{{ rel.join_column }}")
    {% endif %}
    {% if rel.mapped_by %}
    @JoinColumn(mappedBy = "{{ rel.mapped_by }}")
    {% endif %}
    {% endif %}
    private {% if rel.is_collection %}List<{{ rel.target_class }}>{% else %}{{ rel.target_class }}{% endif %} {{ rel.field_name }};
{% endfor %}

    // Default constructor
    public {{ class_name }}() {}

{% for attr in attributes %}
    // Getter for {{ attr.name }}
    public {{ attr.type }} get{{ attr.name | capitalize_first }}() {
        return {{ attr.name }};
    }

    // Setter for {{ attr.name }}
    public void set{{ attr.name | capitalize_first }}({{ attr.type }} {{ attr.name }}) {
        this.{{ attr.name }} = {{ attr.name }};
    }
{% endfor %}

{% for rel in relationships %}
    // Getter for {{ rel.field_name }}
    public {% if rel.is_collection %}List<{{ rel.target_class }}>{% else %}{{ rel.target_class }}{% endif %} get{{ rel.field_name | capitalize_first }}() {
        return {{ rel.field_name }};
    }

    // Setter for {{ rel.field_name }}
    public void set{{ rel.field_name | capitalize_first }}({% if rel.is_collection %}List<{{ rel.target_class }}>{% else %}{{ rel.target_class }}{% endif %} {{ rel.field_name }}) {
        this.{{ rel.field_name }} = {{ rel.field_name }};
    }
{% endfor %}

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
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
                "{{ attr.name }}=" + {{ attr.name }} +{% if not loop.last %}
{% endif %}
{% endfor %}
                '}';
    }
}'''
        
        template = Template(template_str)
        template.environment.filters.update(self.jinja_env.filters)
        return template.render(**context)
    
    def _generate_repository_inline_template(self, context: Dict[str, Any]) -> str:
        """Generate inline JPA Repository template."""
        template_str = '''package {{ package_name }};

{% for import in imports %}
import {{ import }};
{% endfor %}
import {{ entity_package }}.{{ entity_name }};

@Repository
public interface {{ repository_name }} extends JpaRepository<{{ entity_name }}, {{ id_type }}> {

{% for method in custom_methods %}
    /**
     * {{ method.description }}
     */
    {% if method.query_annotation %}
    {{ method.query_annotation }}
    {% endif %}
    {{ method.return_type }} {{ method.name }}({% for param in method.parameters %}{{ param.type }} {{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %});
{% endfor %}

{% for method in query_methods %}
    /**
     * {{ method.description }}
     */
    {% if method.query_annotation %}
    {{ method.query_annotation }}
    {% endif %}
    {{ method.return_type }} {{ method.name }}({% for param in method.parameters %}{{ param.type }} {{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %});
{% endfor %}

{% for method in native_queries %}
    /**
     * {{ method.description }}
     */
    {% if method.modifying %}
    @Modifying
    {% endif %}
    {{ method.query_annotation }}
    {{ method.return_type }} {{ method.name }}({% for param in method.parameters %}@Param("{{ param.name }}") {{ param.type }} {{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %});
{% endfor %}
}'''
        
        template = Template(template_str)
        return template.render(**context)
    
    def _generate_service_inline_template(self, context: Dict[str, Any]) -> str:
        """Generate inline Service template."""
        template_str = '''package {{ package_name }};

{% for import in imports %}
import {{ import }};
{% endfor %}

@Service
@Transactional
public class {{ service_name }} {

    @Autowired
    private {{ repository_name }} {{ entity_name | snake_case }}_repository;

{% for method in crud_methods %}
    /**
     * {{ method.description }}
     */
    {% for annotation in method.annotations %}
    {{ annotation }}
    {% endfor %}
    public {{ method.return_type }} {{ method.name }}({% for param in method.parameters %}{% if param.annotation %}{{ param.annotation }} {% endif %}{{ param.type }} {{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %}) {
        {{ method.implementation }}
    }
{% endfor %}

{% for method in custom_methods %}
    /**
     * {{ method.description }}
     */
    {% for annotation in method.annotations %}
    {{ annotation }}
    {% endfor %}
    public {{ method.return_type }} {{ method.name }}({% for param in method.parameters %}{{ param.type }} {{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %}) {
        {{ method.implementation }}
    }
{% endfor %}

{% for method in dto_mapping_methods %}
    /**
     * {{ method.description }}
     */
    private {{ method.return_type }} {{ method.name }}({% for param in method.parameters %}{{ param.type }} {{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %}) {
        {{ method.implementation }}
    }
{% endfor %}
}'''
        
        template = Template(template_str)
        template.environment.filters.update(self.jinja_env.filters)
        return template.render(**context)
    
    def _generate_controller_inline_template(self, context: Dict[str, Any]) -> str:
        """Generate inline REST Controller template."""
        template_str = '''package {{ package_name }};

{% for import in imports %}
import {{ import }};
{% endfor %}

{% for annotation in class_annotations %}
{{ annotation }}
{% endfor %}
public class {{ controller_name }} {

    @Autowired
    private {{ service_name }} {{ entity_name | snake_case }}_service;

{% for endpoint in crud_endpoints %}
    /**
     * {{ endpoint.name }}
     */
    {% for annotation in endpoint.annotations %}
    {{ annotation }}
    {% endfor %}
    public {{ endpoint.return_type }} {{ endpoint.name }}({% for param in endpoint.parameters %}{{ param.annotation }} {{ param.type }} {{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %}) {
        {{ endpoint.implementation }}
    }
{% endfor %}

{% for endpoint in custom_endpoints %}
    /**
     * {{ endpoint.name }}
     */
    {% for annotation in endpoint.annotations %}
    {{ annotation }}
    {% endfor %}
    public {{ endpoint.return_type }} {{ endpoint.name }}({% for param in endpoint.parameters %}{{ param.annotation }} {{ param.type }} {{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %}) {
        {{ endpoint.implementation }}
    }
{% endfor %}

{% for endpoint in search_endpoints %}
    /**
     * {{ endpoint.name }}
     */
    {% for annotation in endpoint.annotations %}
    {{ annotation }}
    {% endfor %}
    public {{ endpoint.return_type }} {{ endpoint.name }}({% for param in endpoint.parameters %}{{ param.annotation }} {{ param.type }} {{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %}) {
        {{ endpoint.implementation }}
    }
{% endfor %}

{% for handler in exception_handlers %}
    @ExceptionHandler({{ handler.exception }}.class)
    public {{ handler.return_type }} {{ handler.method_name }}({{ handler.exception }} ex) {
        {{ handler.implementation }}
    }
{% endfor %}
}'''
        
        template = Template(template_str)
        template.environment.filters.update(self.jinja_env.filters)
        return template.render(**context)
    
    def _generate_dto_inline_template(self, context: Dict[str, Any]) -> str:
        """Generate inline DTO template."""
        template_str = '''package {{ package_name }};

{% for import in imports %}
import {{ import }};
{% endfor %}

public class {{ dto_name }} {

{% for field in fields %}
    {% for annotation in field.annotations %}
    {{ annotation }}
    {% endfor %}
    private {{ field.type }} {{ field.name }};
{% endfor %}

    // Default constructor
    public {{ dto_name }}() {}

    // Constructor with all fields
    public {{ dto_name }}({% for field in fields %}{{ field.type }} {{ field.name }}{% if not loop.last %}, {% endif %}{% endfor %}) {
{% for field in fields %}
        this.{{ field.name }} = {{ field.name }};
{% endfor %}
    }

{% for field in fields %}
    public {{ field.type }} get{{ field.name | capitalize_first }}() {
        return {{ field.name }};
    }

    public void set{{ field.name | capitalize_first }}({{ field.type }} {{ field.name }}) {
        this.{{ field.name }} = {{ field.name }};
    }
{% endfor %}

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        {{ dto_name }} that = ({{ dto_name }}) o;
        return Objects.equals(id, that.id);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id);
    }

    @Override
    public String toString() {
        return "{{ dto_name }}{" +
{% for field in fields %}
                "{{ field.name }}=" + {{ field.name }} +{% if not loop.last %}
{% endif %}
{% endfor %}
                '}';
    }
}'''
        
        template = Template(template_str)
        template.environment.filters.update(self.jinja_env.filters)
        return template.render(**context)
    
    def _generate_application_inline_template(self, context: Dict[str, Any]) -> str:
        """Generate inline Spring Boot Application template."""
        template_str = '''package {{ package_name }};

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class {{ application_name }} {

    public static void main(String[] args) {
        SpringApplication.run({{ application_name }}.class, args);
    }
}'''
        
        template = Template(template_str)
        return template.render(**context)
    
    def _generate_pom_inline_template(self, context: Dict[str, Any]) -> str:
        """Generate inline Maven pom.xml template."""
        template_str = '''<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         https://maven.apache.org/xsd/maven-4.0.0.xsd">
    
    <modelVersion>4.0.0</modelVersion>
    
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>{{ spring_boot_version }}</version>
        <relativePath/>
    </parent>
    
    <groupId>{{ group_id }}</groupId>
    <artifactId>{{ artifact_id }}</artifactId>
    <version>{{ version }}</version>
    <name>{{ project_name }}</name>
    <description>{{ description }}</description>
    
    <properties>
        <java.version>{{ java_version }}</java.version>
    </properties>
    
    <dependencies>
{% for dependency in dependencies %}
        <dependency>
            <groupId>{{ dependency.group_id }}</groupId>
            <artifactId>{{ dependency.artifact_id }}</artifactId>
            {% if dependency.scope %}<scope>{{ dependency.scope }}</scope>{% endif %}
        </dependency>
{% endfor %}
    </dependencies>
    
    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>'''
        
        template = Template(template_str)
        return template.render(**context)
    
    def _generate_properties_inline_template(self, context: Dict[str, Any]) -> str:
        """Generate inline application.properties template."""
        template_str = '''# Application Configuration
server.port={{ server_port }}
spring.application.name={{ application_name }}

# Database Configuration
spring.datasource.url={{ database_url }}
spring.datasource.username={{ database_username }}
spring.datasource.password={{ database_password }}
spring.datasource.driver-class-name={{ database_driver }}

# JPA Configuration
spring.jpa.hibernate.ddl-auto={{ jpa_ddl_auto }}
spring.jpa.show-sql={{ jpa_show_sql }}
spring.jpa.properties.hibernate.format_sql=true
spring.jpa.properties.hibernate.dialect={{ jpa_dialect }}

# Logging Configuration
logging.level.org.springframework.web={{ log_level_web }}
logging.level.org.hibernate.SQL={{ log_level_sql }}
logging.level.org.hibernate.type.descriptor.sql.BasicBinder={{ log_level_sql_params }}

# OpenAPI Documentation
springdoc.api-docs.path=/api-docs
springdoc.swagger-ui.path=/swagger-ui.html'''
        
        template = Template(template_str)
        return template.render(**context)
    
    def _generate_readme_inline_template(self, context: Dict[str, Any]) -> str:
        """Generate inline README.md template."""
        template_str = '''# {{ project_name }}

{{ description }}

## Getting Started

### Prerequisites

- Java {{ java_version }} or higher
- Maven 3.6 or higher
- {{ database_name }} database

### Installation

1. Clone the repository
```bash
git clone <repository-url>
cd {{ artifact_id }}
```

2. Configure database connection in `application.properties`

3. Build the project
```bash
mvn clean install
```

4. Run the application
```bash
mvn spring-boot:run
```

The application will start on http://localhost:{{ server_port }}

## API Documentation

Once the application is running, you can access the API documentation at:
- Swagger UI: http://localhost:{{ server_port }}/swagger-ui.html
- OpenAPI JSON: http://localhost:{{ server_port }}/api-docs

## Project Structure

```
src/
├── main/java/{{ package_path }}/
│   ├── entities/          # JPA Entity classes
│   ├── repositories/      # JPA Repository interfaces
│   ├── services/          # Business logic services
│   ├── controllers/       # REST API controllers
│   ├── dto/              # Data Transfer Objects
│   └── {{ application_name }}.java  # Main application class
└── main/resources/
    └── application.properties  # Configuration
```

## Generated Entities

{% for entity in entities %}
- **{{ entity.name }}**: {{ entity.description }}
{% endfor %}

## Development

This project was generated from UML diagrams using the FICCT Spring Code platform.

### Building for Production

```bash
mvn clean package -Pprod
```

### Running Tests

```bash
mvn test
```

## License

This project is licensed under the MIT License.'''
        
        template = Template(template_str)
        return template.render(**context)
    
    # Custom Jinja2 filters
    
    def _to_camel_case(self, text: str) -> str:
        """Convert text to camelCase."""
        components = text.split('_')
        return components[0] + ''.join(word.capitalize() for word in components[1:])
    
    def _to_pascal_case(self, text: str) -> str:
        """Convert text to PascalCase."""
        return ''.join(word.capitalize() for word in text.split('_'))
    
    def _to_snake_case(self, text: str) -> str:
        """Convert text to snake_case."""
        import re
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', text).lower()
    
    def _to_kebab_case(self, text: str) -> str:
        """Convert text to kebab-case."""
        import re
        return re.sub('([a-z0-9])([A-Z])', r'\1-\2', text).lower()
    
    def _capitalize_first(self, text: str) -> str:
        """Capitalize first letter of text."""
        return text[0].upper() + text[1:] if text else text
    
    def _format_java_type(self, java_type: str) -> str:
        """Format Java type for template output."""
        return java_type
