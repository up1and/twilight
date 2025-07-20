"""
Test to verify the test setup is working correctly
"""
import os
import sys

def test_python_path():
    """Test that the project root is in Python path"""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    assert project_root in sys.path or any(project_root in p for p in sys.path)

def test_server_import():
    """Test that server modules can be imported"""
    try:
        import server.utils
        import server.models
        import server.services
        import server.app
        assert True
    except ImportError as e:
        assert False, f"Failed to import server modules: {e}"

def test_basic_functionality():
    """Test basic functionality works"""
    from server.utils import upper_case
    result = upper_case("test_string")
    assert result == "Test String"
