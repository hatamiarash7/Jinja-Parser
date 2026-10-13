"""Jinja Parser — a small Flask service that renders Jinja2 templates live.

The service exposes a single-page UI (``GET /``), a rendering API
(``POST /convert``) and a health probe (``GET /healthz``). Templates are
compiled in a sandboxed environment because they are untrusted user input.
"""

import json
from functools import lru_cache
from html import escape

import yaml
from flask import Flask, jsonify, render_template, request
from jinja2 import StrictUndefined, exceptions, select_autoescape
from jinja2.sandbox import ImmutableSandboxedEnvironment
from werkzeug.exceptions import RequestEntityTooLarge

app = Flask(__name__)

# Reject request bodies larger than 1 MiB (basic DoS protection).
MAX_CONTENT_LENGTH = 1 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# Templates bigger than this are compiled on every request so that the
# compilation cache below stays memory-bounded.
CACHEABLE_TEMPLATE_SIZE = 64 * 1024
COMPILE_CACHE_SIZE = 128

# Configure Jinja2 Environment for security and error handling.
# - autoescape: Prevents XSS by escaping HTML characters.
# - undefined: Raises error for undefined variables (aids development).
# - immutable sandbox: Blocks unsafe attribute access (e.g. __class__).
JINJA2_ENVIRONMENT = ImmutableSandboxedEnvironment(
    autoescape=select_autoescape(["html", "xml"]),
    undefined=StrictUndefined,
    enable_async=False,
)


def _compile_template(source: str):
    """Compile ``source`` inside the sandboxed environment (never cached)."""
    return JINJA2_ENVIRONMENT.from_string(source)


_compile_template_cached = lru_cache(maxsize=COMPILE_CACHE_SIZE)(_compile_template)


def get_template(source: str):
    """Return a compiled template, using a bounded cache for small templates.

    Rendering the same template repeatedly (the typical interactive usage)
    skips recompilation, while oversized templates bypass the cache so a
    hostile client cannot pin unbounded memory.
    """
    if len(source) <= CACHEABLE_TEMPLATE_SIZE:
        return _compile_template_cached(source)
    return _compile_template(source)


@app.errorhandler(RequestEntityTooLarge)
def handle_request_too_large(_error):
    """Return a JSON error when the request body exceeds the size limit."""
    limit_kb = MAX_CONTENT_LENGTH // 1024
    return jsonify(
        {"error": f"Request body too large. The maximum is {limit_kb} KB."}
    ), 413


@app.route("/", methods=["GET"])
def home():
    """Render the home page (index.html)."""
    return render_template("index.html")


@app.route("/healthz", methods=["GET"])
def healthz():
    """Liveness probe used by the Docker healthcheck and orchestrators."""
    return jsonify({"status": "ok"}), 200


@app.route("/convert", methods=["POST"])
def convert():
    """
    Handle POST requests to render a Jinja2 template.

    Expects the form fields ``template``, ``type`` (``json`` or ``yaml``),
    ``values`` and the optional ``whitespaces`` flag. Returns a JSON
    response with ``rendered_output`` (200) or ``error`` (400/500).
    """
    # 1. Input retrieval and validation
    template_string: str = request.form.get("template", "").strip()
    input_type: str = request.form.get("type", "").lower()
    values_string: str = request.form.get("values", "").strip()
    whitespaces_flag: str = request.form.get("whitespaces", "0")

    if not template_string:
        return jsonify({"error": "Template field cannot be empty."}), 400

    show_whitespaces: bool = (
        bool(int(whitespaces_flag)) if whitespaces_flag.isdigit() else False
    )

    # 2. Jinja2 template compilation
    try:
        jinja2_tpl = get_template(template_string)
    except (exceptions.TemplateSyntaxError, exceptions.TemplateError) as e:
        return jsonify({"error": f"Syntax error in Jinja2 template: {e}"}), 400
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Last-resort guard: untrusted input must never crash the worker.
        app.logger.exception("Unexpected error while compiling the template")
        return jsonify(
            {"error": f"An unexpected error occurred during template compilation: {e}"}
        ), 500

    # 3. Variable data processing
    if not values_string:
        return jsonify({"error": "Values field cannot be empty."}), 400

    template_variables: dict = {}

    if input_type == "json":
        try:
            template_variables = json.loads(values_string)
        except json.JSONDecodeError as e:
            return jsonify(
                {"error": f"JSON decode error: {e}. Please ensure your JSON is valid."}
            ), 400
    elif input_type == "yaml":
        try:
            # IMPORTANT: Use yaml.safe_load() for security.
            template_variables = yaml.safe_load(values_string)
        except yaml.YAMLError as e:
            return jsonify(
                {"error": f"YAML parse error: {e}. Please ensure your YAML is valid."}
            ), 400
    else:
        return jsonify(
            {
                "error": (
                    f"Undefined or unsupported input type: '{escape(input_type)}'. "
                    "Supported types are 'json' and 'yaml'."
                )
            }
        ), 400

    if not isinstance(template_variables, dict):
        return jsonify(
            {
                "error": (
                    f"Provided {input_type} data is not a dictionary. Template "
                    "variables must be provided as a dictionary "
                    "(e.g., {'key': 'value'})."
                )
            }
        ), 400

    # 4. Jinja2 template rendering
    try:
        rendered_jinja2_tpl: str = jinja2_tpl.render(template_variables)
    except (exceptions.TemplateRuntimeError, ValueError, TypeError) as e:
        return jsonify(
            {
                "error": (
                    f"Error during template rendering: {e}. Check your template "
                    "variables and their types."
                )
            }
        ), 400
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Last-resort guard: untrusted input must never crash the worker.
        app.logger.exception("Unexpected error while rendering the template")
        return jsonify(
            {"error": f"An unexpected error occurred during template rendering: {e}"}
        ), 500

    # 5. Post-processing: replace whitespaces if requested
    if show_whitespaces:
        rendered_jinja2_tpl = rendered_jinja2_tpl.replace(" ", "•")

    # 6. Final output preparation
    # Escape final output for XSS prevention if inserted into HTML.
    final_output: str = escape(rendered_jinja2_tpl).replace("\n", "<br />")

    return jsonify({"rendered_output": final_output}), 200


if __name__ == "__main__":
    app.run(debug=False)
