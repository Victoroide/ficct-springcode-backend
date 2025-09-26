@echo off
REM Script para ejecutar pruebas específicas con la configuración correcta
echo Ejecutando pruebas...
set PYTHONPATH=%PYTHONPATH%;c:\Users\PC Gamer\Desktop\Repositories\python\django\ficct-springcode-backend
echo Pruebas de sistema:
python manage.py test base.test_system_endpoints --keepdb

echo.
echo Pruebas del módulo de proyectos:
python manage.py test apps.projects.tests.test_models.WorkspaceModelTestCase apps.projects.tests.test_models.ProjectModelTestCase apps.projects.tests.test_models.ProjectTemplateModelTestCase --keepdb
