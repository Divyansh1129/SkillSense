import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="skillsense_test_")
os.environ["SKILLSENSE_DATA"] = _tmp          # isolate test data/DB; must be set before importing app.*
os.environ["ENABLE_SCHEDULER"] = "0"
