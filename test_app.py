# test_app.py
import json

import pytest

from app import app


@pytest.fixture
def client():
    """Flask test client fixture."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# ----------------------------------------------------------------------
# Basic functionality tests
# ----------------------------------------------------------------------
def test_home_route(client):
    """GET / returns the home page."""
    response = client.get("/")
    assert response.status_code == 200
    # Adjust based on your actual index.html content
    assert b"Jinja2" in response.data or b"Template" in response.data


def test_convert_with_json(client):
    """POST /convert with valid JSON."""
    template = "Hello {{ name }}!"
    data = {
        "template": template,
        "type": "json",
        "values": json.dumps({"name": "World"}),
        "dummy": "0",
        "whitespaces": "0",
    }
    response = client.post("/convert", data=data)
    assert response.status_code == 200
    json_resp = response.get_json()
    assert json_resp["rendered_output"] == "Hello World!"


def test_convert_with_yaml(client):
    """POST /convert with valid YAML."""
    template = "Hello {{ name }}!"
    data = {
        "template": template,
        "type": "yaml",
        "values": "name: YAML",
        "dummy": "0",
        "whitespaces": "0",
    }
    response = client.post("/convert", data=data)
    assert response.status_code == 200
    json_resp = response.get_json()
    assert json_resp["rendered_output"] == "Hello YAML!"


def test_whitespace_replacement(client):
    """POST /convert with whitespace replacement enabled."""
    template = "Hello World"
    data = {
        "template": template,
        "type": "json",
        "values": "{}",
        "dummy": "0",
        "whitespaces": "1",
    }
    response = client.post("/convert", data=data)
    assert response.status_code == 200
    json_resp = response.get_json()
    # Output has spaces replaced with '•'
    assert json_resp["rendered_output"] == "Hello•World"


# ----------------------------------------------------------------------
# Error handling tests
# ----------------------------------------------------------------------
def test_empty_template(client):
    """Empty template returns error."""
    data = {
        "template": "",
        "type": "json",
        "values": "{}",
        "dummy": "0",
        "whitespaces": "0",
    }
    response = client.post("/convert", data=data)
    assert response.status_code == 400
    json_resp = response.get_json()
    assert "error" in json_resp
    assert "Template field cannot be empty" in json_resp["error"]


def test_syntax_error_in_template(client):
    """Jinja2 syntax error returns 400."""
    template = "{% if true %}"  # missing endif
    data = {
        "template": template,
        "type": "json",
        "values": "{}",
        "dummy": "0",
        "whitespaces": "0",
    }
    response = client.post("/convert", data=data)
    assert response.status_code == 400
    json_resp = response.get_json()
    assert "Syntax error" in json_resp["error"]


def test_missing_values_when_no_dummy(client):
    """Missing values string with dummy=0 returns 400."""
    data = {
        "template": "{{ name }}",
        "type": "json",
        "values": "",
        "dummy": "0",
        "whitespaces": "0",
    }
    response = client.post("/convert", data=data)
    assert response.status_code == 400
    json_resp = response.get_json()
    assert "Values field cannot be empty" in json_resp["error"]


def test_invalid_json(client):
    """Invalid JSON returns 400."""
    data = {
        "template": "{{ name }}",
        "type": "json",
        "values": "{bad json}",
        "dummy": "0",
        "whitespaces": "0",
    }
    response = client.post("/convert", data=data)
    assert response.status_code == 400
    json_resp = response.get_json()
    assert "JSON decode error" in json_resp["error"]


def test_invalid_yaml(client):
    """Invalid YAML returns 400."""
    data = {
        "template": "{{ name }}",
        "type": "yaml",
        "values": "bad: yaml: :",
        "dummy": "0",
        "whitespaces": "0",
    }
    response = client.post("/convert", data=data)
    assert response.status_code == 400
    json_resp = response.get_json()
    assert "YAML parse error" in json_resp["error"]


def test_unsupported_type(client):
    """Unsupported input type returns 400."""
    data = {
        "template": "{{ name }}",
        "type": "xml",
        "values": "<name>test</name>",
        "dummy": "0",
        "whitespaces": "0",
    }
    response = client.post("/convert", data=data)
    assert response.status_code == 400
    json_resp = response.get_json()
    assert "Undefined or unsupported input_type" in json_resp["error"]


def test_non_dict_data(client):
    """JSON/YAML data that is not a dict returns 400."""
    data = {
        "template": "{{ name }}",
        "type": "json",
        "values": '["list", "not", "dict"]',
        "dummy": "0",
        "whitespaces": "0",
    }
    response = client.post("/convert", data=data)
    assert response.status_code == 400
    json_resp = response.get_json()
    assert "not a dictionary" in json_resp["error"]


def test_undefined_variable_without_dummy(client):
    """Rendering with undefined variable raises error (StrictUndefined)."""
    data = {
        "template": "Hello {{ undefined_var }}",
        "type": "json",
        "values": "{}",
        "dummy": "0",
        "whitespaces": "0",
    }
    response = client.post("/convert", data=data)
    assert response.status_code == 400
    json_resp = response.get_json()
    assert "Error during template rendering" in json_resp["error"]


# ----------------------------------------------------------------------
# Security tests: Template Injection (SSTI) prevention
# ----------------------------------------------------------------------
def test_ssti_basic_math(client):
    """Simple math expression is safe; sandbox allows arithmetic."""
    # SandboxedEnvironment allows math, but we test it renders as expected.
    template = "{{ 7*7 }}"
    data = {
        "template": template,
        "type": "json",
        "values": "{}",
        "dummy": "0",
        "whitespaces": "0",
    }
    response = client.post("/convert", data=data)
    assert response.status_code == 200
    json_resp = response.get_json()
    # Arithmetic is allowed, output is '49'
    assert json_resp["rendered_output"] == "49"


def test_ssti_config_access_blocked(client):
    """Flask config should not be accessible because environment is isolated."""
    template = "{{ config }}"
    data = {
        "template": template,
        "type": "json",
        "values": "{}",
        "dummy": "0",
        "whitespaces": "0",
    }
    response = client.post("/convert", data=data)
    # Should raise StrictUndefined because 'config' is not provided in variables
    assert response.status_code == 400
    json_resp = response.get_json()
    assert "Error during template rendering" in json_resp["error"]


def test_ssti_builtins_blocked(client):
    """Access to Python builtins via __builtins__ is blocked by sandbox."""
    template = "{{ ''.__class__.__mro__[1].__subclasses__() }}"
    data = {
        "template": template,
        "type": "json",
        "values": "{}",
        "dummy": "0",
        "whitespaces": "0",
    }
    response = client.post("/convert", data=data)
    # SandboxedEnvironment should raise a SecurityError
    assert response.status_code == 400
    json_resp = response.get_json()
    # The error may be a SecurityError during rendering
    assert (
        "Error during template rendering" in json_resp["error"]
        or "SecurityError" in json_resp["error"]
    )


def test_ssti_file_read_blocked(client):
    """Attempt to read /etc/passwd should be blocked."""
    template = (
        "{{ ''.__class__.__mro__[1].__subclasses__()[40]('/etc/passwd').read() }}"
    )
    data = {
        "template": template,
        "type": "json",
        "values": "{}",
        "dummy": "0",
        "whitespaces": "0",
    }
    response = client.post("/convert", data=data)
    assert response.status_code == 400
    json_resp = response.get_json()
    assert "Error during template rendering" in json_resp["error"]


def test_ssti_request_object_blocked(client):
    """Flask request object is not available."""
    template = "{{ request }}"
    data = {
        "template": template,
        "type": "json",
        "values": "{}",
        "dummy": "0",
        "whitespaces": "0",
    }
    response = client.post("/convert", data=data)
    assert response.status_code == 400
    json_resp = response.get_json()
    assert "Error during template rendering" in json_resp["error"]


def test_ssti_import_blocked(client):
    """Import statement blocked by sandbox."""
    template = "{% import os %}{{ os.popen('ls').read() }}"
    data = {
        "template": template,
        "type": "json",
        "values": "{}",
        "dummy": "0",
        "whitespaces": "0",
    }
    response = client.post("/convert", data=data)
    assert response.status_code == 400
    json_resp = response.get_json()
    # Jinja2 import is not allowed; should raise an error
    assert "error" in json_resp["error"]


def test_ssti_safe_string_escaping(client):
    """HTML output is escaped to prevent XSS."""
    template = "<script>alert('xss')</script>"
    data = {
        "template": template,
        "type": "json",
        "values": "{}",
        "dummy": "0",
        "whitespaces": "0",
    }
    response = client.post("/convert", data=data)
    assert response.status_code == 200
    json_resp = response.get_json()
    # The rendered output is escaped (e.g., &lt;script&gt;)
    assert "&lt;script&gt;" in json_resp["rendered_output"]


# ----------------------------------------------------------------------
# Edge cases and additional coverage
# ----------------------------------------------------------------------
def test_large_template(client):
    """Large template is handled without crashing."""
    template = "x" * 10000  # 10k chars, adjust based on your MAX_TEMPLATE_SIZE
    data = {
        "template": template,
        "type": "json",
        "values": "{}",
        "dummy": "0",
        "whitespaces": "0",
    }
    response = client.post("/convert", data=data)
    # Should succeed unless you've added a size limit
    assert response.status_code == 200
