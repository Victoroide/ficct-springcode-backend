@echo off
REM Script para ejecutar solo los tests de los modulos de Project

SET PYTHONPATH=%PYTHONPATH%;c:\Users\PC Gamer\Desktop\Repositories\python\django\ficct-springcode-backend
SET DJANGO_SETTINGS_MODULE=base.settings

echo Ejecutando pruebas de modelos de Workspace...
python manage.py test apps.projects.tests.test_models.WorkspaceModelTestCase --keepdb

echo.
echo Ejecutando pruebas de modelos de Project...
python manage.py test apps.projects.tests.test_models.ProjectModelTestCase --keepdb

echo.
echo Ejecutando pruebas de modelos de ProjectTemplate...
python manage.py test apps.projects.tests.test_models.ProjectTemplateModelTestCase --keepdb
