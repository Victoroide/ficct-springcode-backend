"""
Script para ejecutar las pruebas específicas de proyectos.

Este script ejecuta los tests de los módulos de WorkspaceModelTestCase,
ProjectModelTestCase y ProjectTemplateModelTestCase.
"""
import os
import sys
import django
from django.test.runner import DiscoverRunner

# Asegúrate de que este archivo se ejecuta desde el directorio correcto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != BASE_DIR:
    os.chdir(BASE_DIR)

# Configurar el entorno de Django
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "base.settings")
django.setup()

# Test runner personalizado para ejecutar tests específicos
class SpecificTestRunner:
    def run_tests(self):
        """Ejecuta los tests de los modelos de Project"""
        test_labels = [
            'apps.projects.tests.test_models.WorkspaceModelTestCase',
            'apps.projects.tests.test_models.ProjectModelTestCase',
            'apps.projects.tests.test_models.ProjectTemplateModelTestCase'
        ]
        
        test_runner = DiscoverRunner(verbosity=1, keepdb=True)
        failures = test_runner.run_tests(test_labels)
        
        return failures

if __name__ == "__main__":
    test_runner = SpecificTestRunner()
    failures = test_runner.run_tests()
    sys.exit(failures)
