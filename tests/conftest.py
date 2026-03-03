import sys
import os

# Add project root to path so calculator and data modules are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c
