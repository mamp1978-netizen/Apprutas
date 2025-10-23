# Forzar que cualquier "import app_utils_core as app_utils" use app_utils_core
import sys, importlib
sys.modules['app_utils'] = importlib.import_module('app_utils_core')
