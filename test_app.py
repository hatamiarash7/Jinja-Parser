"""Tests for the Jinja Parser Flask application."""

# Test functions take pytest fixtures as arguments whose names intentionally
# match the fixture names, which pylint flags as shadowing an outer scope.
# pylint: disable=redefined-outer-name

import json

import pytest

from app import CACHEABLE_TEMPLATE_SIZE, MAX_CONTENT_LENGTH, app


@pytest.fixture
def client():
    """Flask test client fixture."""
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def post_convert(
    client,
    template="Hello {{ name }}!",
    values=None,
    input_type="json",
    whitespaces="0",
):
    """POST a conversion request with sensible defaults."""
    return client.post(
        "/convert",
        data={
            "template": template,
            "type": input_type,
            "values": '{"name": "World"}' if values is None else values,
            "whitespaces": whitespaces,
        },
    )


# ----------------------------------------------------------------------
# Home page and health probe
# ----------------------------------------------------------------------
def test_home_route(client):
    """GET / returns the home page."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Jinja Parser" in response.data
    assert b'<textarea id="template"' in response.data


def test_home_post_not_allowed(client):
    """POST / is not allowed."""
    response = client.post("/")
    assert response.status_code == 405


def test_healthz(client):
    """GET /healthz returns an ok status."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


# ----------------------------------------------------------------------
# Basic functionality
# ----------------------------------------------------------------------
def test_convert_with_json(client):
    """POST /convert with valid JSON values."""
    response = post_convert(client)
    assert response.status_code == 200
    assert response.get_json()["rendered_output"] == "Hello World!"


def test_convert_with_yaml(client):
    """POST /convert with valid YAML values."""
    response = post_convert(client, values="name: YAML", input_type="yaml")
    assert response.status_code == 200
    assert response.get_json()["rendered_output"] == "Hello YAML!"


def test_convert_type_is_case_insensitive(client):
    """An uppercase 'type' value is normalized to lowercase."""
    response = post_convert(client, input_type="JSON")
    assert response.status_code == 200
    assert response.get_json()["rendered_output"] == "Hello World!"


def test_convert_response_is_json(client):
    """The API returns a JSON content type."""
    response = post_convert(client)
    assert response.content_type == "application/json"


def test_whitespace_replacement_enabled(client):
    """whitespaces=1 replaces spaces with bullets."""
    response = post_convert(
        client, template="Hello World", values="{}", whitespaces="1"
    )
    assert response.status_code == 200
    assert response.get_json()["rendered_output"] == "Hello•World"


def test_whitespace_replacement_disabled(client):
    """whitespaces=0 keeps spaces intact."""
    response = post_convert(
        client, template="Hello World", values="{}", whitespaces="0"
    )
    assert response.status_code == 200
    assert response.get_json()["rendered_output"] == "Hello World"


def test_whitespace_flag_non_numeric_is_false(client):
    """A non-numeric whitespaces flag is treated as disabled."""
    response = post_convert(
        client, template="Hello World", values="{}", whitespaces="true"
    )
    assert response.status_code == 200
    assert response.get_json()["rendered_output"] == "Hello World"


def test_newlines_become_br_tags(client):
    """Newlines in the rendered output are converted to <br />."""
    response = post_convert(client, template="line1\nline2", values="{}")
    assert response.status_code == 200
    assert response.get_json()["rendered_output"] == "line1<br />line2"


def test_loop_and_filters(client):
    """Loops, filters and nested data structures render correctly."""
    values = json.dumps({"items": ["a", "b", "c"], "nested": {"key": "value"}})
    response = post_convert(
        client,
        template="{% for item in items %}{{ item | upper }}{% endfor %} {{ nested.key }}",
        values=values,
    )
    assert response.status_code == 200
    assert response.get_json()["rendered_output"] == "ABC value"


def test_large_template_bypasses_cache(client):
    """Templates larger than the cacheable size still render."""
    template = "x" * (CACHEABLE_TEMPLATE_SIZE + 1)
    response = post_convert(client, template=template, values="{}")
    assert response.status_code == 200
    assert response.get_json()["rendered_output"] == template


def test_same_template_twice(client):
    """A cached template can be rendered again with different values."""
    assert post_convert(client).status_code == 200
    second = post_convert(client, values='{"name": "Again"}')
    assert second.status_code == 200
    assert second.get_json()["rendered_output"] == "Hello Again!"


# ----------------------------------------------------------------------
# Input validation errors
# ----------------------------------------------------------------------
def test_empty_template(client):
    """An empty template returns a 400 error."""
    response = post_convert(client, template="", values="{}")
    assert response.status_code == 400
    assert "Template field cannot be empty" in response.get_json()["error"]


def test_whitespace_only_template(client):
    """A whitespace-only template is treated as empty."""
    response = post_convert(client, template="   \n\t ", values="{}")
    assert response.status_code == 400
    assert "Template field cannot be empty" in response.get_json()["error"]


def test_empty_values(client):
    """Empty values return a 400 error."""
    response = post_convert(client, values="")
    assert response.status_code == 400
    assert "Values field cannot be empty" in response.get_json()["error"]


def test_whitespace_only_values(client):
    """Whitespace-only values are treated as empty."""
    response = post_convert(client, values="   ")
    assert response.status_code == 400
    assert "Values field cannot be empty" in response.get_json()["error"]


def test_syntax_error_in_template(client):
    """A Jinja2 syntax error returns a 400 error."""
    response = post_convert(client, template="{% if true %}", values="{}")
    assert response.status_code == 400
    assert "Syntax error" in response.get_json()["error"]


def test_unterminated_variable(client):
    """An unterminated variable expression is a syntax error."""
    response = post_convert(client, template="{{ name ", values="{}")
    assert response.status_code == 400
    assert "Syntax error" in response.get_json()["error"]


def test_invalid_json(client):
    """Invalid JSON returns a 400 error."""
    response = post_convert(client, values="{bad json}")
    assert response.status_code == 400
    assert "JSON decode error" in response.get_json()["error"]


def test_invalid_yaml(client):
    """Invalid YAML returns a 400 error."""
    response = post_convert(client, values="bad: yaml: :", input_type="yaml")
    assert response.status_code == 400
    assert "YAML parse error" in response.get_json()["error"]


def test_unsupported_type(client):
    """An unsupported input type returns a 400 error."""
    response = post_convert(client, values="<name>test</name>", input_type="xml")
    assert response.status_code == 400
    assert "Undefined or unsupported input type" in response.get_json()["error"]


def test_unsupported_type_is_escaped(client):
    """HTML characters in the unsupported type are escaped in the error."""
    response = post_convert(client, values="{}", input_type="<script>")
    assert response.status_code == 400
    assert "&lt;script&gt;" in response.get_json()["error"]
    assert "<script>" not in response.get_json()["error"]


@pytest.mark.parametrize(
    "input_type,payload",
    [
        ("json", '["list", "not", "dict"]'),
        ("json", '"just a string"'),
        ("json", "42"),
        ("json", "null"),
        ("yaml", "42"),
        ("yaml", "just a scalar"),
    ],
)
def test_non_dict_values(client, input_type, payload):
    """Values that do not parse to a dictionary return a 400 error."""
    response = post_convert(client, values=payload, input_type=input_type)
    assert response.status_code == 400
    assert "not a dictionary" in response.get_json()["error"]


def test_yaml_null_is_not_a_dict(client):
    """YAML 'null' is not a dictionary."""
    response = post_convert(client, values="null", input_type="yaml")
    assert response.status_code == 400
    assert "not a dictionary" in response.get_json()["error"]


def test_request_body_too_large(client):
    """Bodies larger than MAX_CONTENT_LENGTH are rejected with 413."""
    response = post_convert(
        client, template="x" * (MAX_CONTENT_LENGTH + 1), values="{}"
    )
    assert response.status_code == 413
    assert "Request body too large" in response.get_json()["error"]


def test_convert_get_not_allowed(client):
    """GET /convert is not allowed."""
    response = client.get("/convert")
    assert response.status_code == 405


# ----------------------------------------------------------------------
# Rendering errors
# ----------------------------------------------------------------------
def test_undefined_variable(client):
    """An undefined variable raises an error (StrictUndefined)."""
    response = post_convert(client, template="Hello {{ undefined_var }}", values="{}")
    assert response.status_code == 400
    assert "Error during template rendering" in response.get_json()["error"]


def test_render_type_error(client):
    """A type error during rendering returns a 400 error."""
    response = post_convert(client, template='{{ "%d" | format("x") }}', values="{}")
    assert response.status_code == 400
    assert "Error during template rendering" in response.get_json()["error"]


def test_render_value_error(client):
    """A value error during rendering returns a 400 error."""
    response = post_convert(client, template='{{ "{:.2q}".format(1) }}', values="{}")
    assert response.status_code == 400
    assert "Error during template rendering" in response.get_json()["error"]


def test_unexpected_compile_error(client, monkeypatch):
    """Unexpected exceptions during compilation return a 500 error."""

    def _boom(_source):
        """Raise instead of compiling a template."""
        raise RuntimeError("boom")

    monkeypatch.setattr("app.get_template", _boom)
    response = post_convert(client)
    assert response.status_code == 500
    assert (
        "unexpected error occurred during template compilation"
        in response.get_json()["error"]
    )


def test_unexpected_render_error(client, monkeypatch):
    """Unexpected exceptions during rendering return a 500 error."""

    class _BoomTemplate:
        """Stub template that raises instead of rendering."""

        @staticmethod
        def render(_variables):
            """Raise instead of rendering."""
            raise RuntimeError("boom")

    monkeypatch.setattr("app.get_template", lambda _source: _BoomTemplate())
    response = post_convert(client)
    assert response.status_code == 500
    assert (
        "unexpected error occurred during template rendering"
        in response.get_json()["error"]
    )


# ----------------------------------------------------------------------
# Security: template injection (SSTI) prevention
# ----------------------------------------------------------------------
def test_ssti_basic_math_is_allowed(client):
    """Arithmetic is safe and renders as expected."""
    response = post_convert(client, template="{{ 7*7 }}", values="{}")
    assert response.status_code == 200
    assert response.get_json()["rendered_output"] == "49"


def test_ssti_attribute_access_blocked(client):
    """Access to unsafe attributes via __class__ is blocked."""
    response = post_convert(
        client, template="{{ ''.__class__.__mro__[1].__subclasses__() }}", values="{}"
    )
    assert response.status_code == 400


def test_ssti_attr_filter_bypass_blocked(client):
    """The |attr filter cannot be used to reach unsafe attributes."""
    response = post_convert(client, template='{{ ""|attr("__class__") }}', values="{}")
    assert response.status_code == 400


def test_ssti_globals_access_blocked(client):
    """Function __globals__ are not reachable."""
    response = post_convert(client, template="{{ lipsum.__globals__ }}", values="{}")
    assert response.status_code == 400


def test_ssti_template_reference_blocked(client):
    """The internal template reference context is not reachable."""
    response = post_convert(
        client,
        template="{{ self._TemplateReference__context.cycler.__init__.__globals__ }}",
        values="{}",
    )
    assert response.status_code == 400


def test_ssti_include_without_loader(client):
    """{% include %} fails because the sandbox has no template loader."""
    response = post_convert(client, template="{% include 'index.html' %}", values="{}")
    assert response.status_code == 400


def test_ssti_import_without_loader(client):
    """{% import %} fails because the sandbox has no template loader."""
    response = post_convert(
        client, template="{% import 'index.html' as x %}{{ x }}", values="{}"
    )
    assert response.status_code == 400


def test_ssti_flask_objects_not_available(client):
    """Flask objects such as config and request are not defined."""
    for template in ("{{ config }}", "{{ request }}"):
        response = post_convert(client, template=template, values="{}")
        assert response.status_code == 400, template


def test_jinja_globals_render_harmlessly(client):
    """Standard Jinja globals exist but only stringify to harmless text."""
    for template in ("{{ self }}", "{{ namespace }}"):
        response = post_convert(client, template=template, values="{}")
        assert response.status_code == 200, template
        assert "<" not in response.get_json()["rendered_output"]


def test_yaml_deserialization_attack_blocked(client):
    """yaml.safe_load refuses to construct arbitrary Python objects."""
    response = post_convert(
        client,
        values="!!python/object/apply:os.system ['echo pwned']",
        input_type="yaml",
    )
    assert response.status_code == 400
    assert "YAML parse error" in response.get_json()["error"]


def test_output_html_is_escaped(client):
    """Rendered output is HTML-escaped to prevent XSS."""
    values = json.dumps({"name": "<script>alert('xss')</script>"})
    response = post_convert(client, template="Hello {{ name }}", values=values)
    assert response.status_code == 200
    rendered = response.get_json()["rendered_output"]
    # Variable output is escaped twice (autoescape + final escape): safe
    # over-escaping, never under-escaping.
    assert "<script>" not in rendered
    assert "&amp;lt;script&amp;gt;" in rendered


def test_literal_template_html_is_escaped(client):
    """HTML that is part of the template itself is escaped too."""
    response = post_convert(
        client, template="<script>alert('xss')</script>", values="{}"
    )
    assert response.status_code == 200
    assert "&lt;script&gt;" in response.get_json()["rendered_output"]
