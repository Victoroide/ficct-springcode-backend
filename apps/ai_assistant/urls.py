from django.urls import path
from . import views

app_name = 'ai_assistant'

urlpatterns = [
    path('ask/', views.ask_ai_assistant, name='ask'),
    path('ask-about-diagram/<uuid:diagram_id>/', views.ask_about_diagram, name='ask_about_diagram'),
    path('analysis/<uuid:diagram_id>/', views.get_diagram_analysis, name='diagram_analysis'),
    path('statistics/', views.get_system_statistics, name='system_statistics'),
    path('health/', views.ai_assistant_health, name='health'),

    path('process-command/', views.process_uml_command, name='process_uml_command'),
    path('process-command/<uuid:diagram_id>/', views.process_uml_command_for_diagram, name='process_uml_command_for_diagram'),
    path('supported-commands/', views.get_supported_commands, name='get_supported_commands'),
]
