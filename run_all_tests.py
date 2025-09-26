#!/usr/bin/env python
"""
Script robusto para ejecutar tests en Django usando el comando básico 'test'.
"""

import os
import sys
import subprocess

def run_tests():
    """Ejecuta todas las pruebas con manejo de errores."""
    # Ejecutar el comando básico de test
    print("\n=== Ejecutando todas las pruebas de Django ===")
    process = subprocess.run([
        "python", 
        "manage.py", 
        "test", 
        "--keepdb"
    ])
    
    return process.returncode

if __name__ == "__main__":
    sys.exit(run_tests())
