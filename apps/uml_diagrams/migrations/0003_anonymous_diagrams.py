# Generated for anonymous UML diagrams refactoring
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('uml_diagrams', '0002_add_public_access_fields'),
    ]

    operations = [
        # Drop old table first
        migrations.RunSQL(
            "DROP TABLE IF EXISTS uml_diagrams CASCADE;",
            reverse_sql="-- Cannot reverse table drop"
        ),
        
        # Create new anonymous table
        migrations.CreateModel(
            name='UMLDiagram',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(default='Untitled Diagram', max_length=200)),
                ('description', models.TextField(blank=True)),
                ('session_id', models.CharField(db_index=True, help_text='Session ID of the creator/last editor', max_length=64)),
                ('diagram_type', models.CharField(choices=[('CLASS', 'Class Diagram'), ('SEQUENCE', 'Sequence Diagram'), ('USE_CASE', 'Use Case Diagram'), ('ACTIVITY', 'Activity Diagram'), ('STATE', 'State Diagram'), ('COMPONENT', 'Component Diagram'), ('DEPLOYMENT', 'Deployment Diagram')], default='CLASS', max_length=15)),
                ('content', models.JSONField(default=dict, help_text='Complete UML diagram structure and elements')),
                ('layout_config', models.JSONField(default=dict, help_text='Diagram layout and positioning')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_modified', models.DateTimeField(auto_now=True)),
                ('active_sessions', models.JSONField(default=list, help_text='List of currently active sessions viewing/editing')),
            ],
            options={
                'db_table': 'uml_diagrams',
                'ordering': ['-last_modified'],
            },
        ),
        
        # Add indexes
        migrations.AddIndex(
            model_name='umldiagram',
            index=models.Index(fields=['session_id', 'created_at'], name='uml_diagrams_session_created_idx'),
        ),
        migrations.AddIndex(
            model_name='umldiagram',
            index=models.Index(fields=['created_at'], name='uml_diagrams_created_idx'),
        ),
        migrations.AddIndex(
            model_name='umldiagram',
            index=models.Index(fields=['last_modified'], name='uml_diagrams_modified_idx'),
        ),
        migrations.AddIndex(
            model_name='umldiagram',
            index=models.Index(fields=['diagram_type'], name='uml_diagrams_type_idx'),
        ),
    ]
