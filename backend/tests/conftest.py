import os
import sys
from pathlib import Path

# The module-level check in app.core.config would abort the import of a test environment without real
# secrets; the tests call check_security()/check_initial_admin_password() explicitly instead.
os.environ["GUAYNET_SKIP_SECURITY_CHECK"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
