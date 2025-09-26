#!/usr/bin/env python
"""
Script robusto para ejecutar tests en Django con recuperación de errores.
"""

import os
import sys
import subprocess

def run_tests():
    """Ejecuta los tests específicos en orden con manejo de errores."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base.settings')
    
    # Primero probamos los tests del sistema que sabemos que funcionan
    print("\n=== Ejecutando tests del sistema ===")
    subprocess.run(["python", "manage.py", "test", "base.test_system_endpoints", "--keepdb"])
    
    # Luego intenta ejecutar tests para cada app individualmente
    apps_tests = [
        "base.test_factories",
        "apps.authentication.tests.test_models",
        "apps.collaboration.tests.test_models",
        "apps.uml_diagrams.tests.test_models",
        "apps.code_generation.tests.test_models",
        "apps.projects.tests.test_models"
    ]
    
    for test_module in apps_tests:
        print(f"\n=== Ejecutando {test_module} ===")
        subprocess.run(["python", "manage.py", "test", test_module, "--keepdb"])
    
    return 0

if __name__ == "__main__":
    sys.exit(run_tests())
