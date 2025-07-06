# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function

import json
from html import escape
from random import choice

import yaml
from flask import Flask, jsonify, render_template, request
from jinja2 import Environment, StrictUndefined, exceptions, meta, select_autoescape

app = Flask(__name__)

DUMMY_VALUES = [
    "Lorem",
    "Ipsum",
    "Amet",
    "Elit",
    "Expositum",
    "Dissimile",
    "Superiori",
    "Laboro",
    "Torquate",
    "sunt",
]

# Configure Jinja2 Environment for security and error handling.
# - autoescape: Prevents XSS by escaping HTML characters.
# - undefined: Raises error for undefined variables (aids development).
JINJA2_ENVIRONMENT = Environment(
    autoescape=select_autoescape(["html", "xml"]),
    undefined=StrictUndefined,
)


@app.route("/")
def home():
    """Renders the home page (index.html)."""
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert():
    """
    Handles POST requests to render a Jinja2 template.
    Expects 'template', 'type', 'values', 'dummy', 'whitespaces' from input.
    Returns JSON response with 'rendered_output' or 'error'.
    """
    # 1. Input Retrieval and Validation
    template_string = request.form.get("template", "").strip()
    input_type = request.form.get("type", "").lower()
    values_string = request.form.get("values", "").strip()
    dummy_flag = request.form.get("dummy", "0")
    whitespaces_flag = request.form.get("whitespaces", "0")

    if not template_string:
        return jsonify({"error": "Template field cannot be empty."}), 400

    use_dummy_data = bool(int(dummy_flag)) if dummy_flag.isdigit() else False
    show_whitespaces = (
        bool(int(whitespaces_flag)) if whitespaces_flag.isdigit() else False
    )

    # 2. Jinja2 Template Compilation
    try:
        jinja2_tpl = JINJA2_ENVIRONMENT.from_string(template_string)
    except (exceptions.TemplateSyntaxError, exceptions.TemplateError) as e:
        return jsonify({"error": f"Syntax error in Jinja2 template: {e}"}), 400
    except Exception as e:
        return jsonify(
            {"error": f"An unexpected error occurred during template compilation: {e}"}
        ), 500

    # 3. Variable Data Processing
    template_variables = {}
    if use_dummy_data:
        try:
            parsed_template = JINJA2_ENVIRONMENT.parse(template_string)
            vars_to_fill = meta.find_undeclared_variables(parsed_template)
            for var in vars_to_fill:
                template_variables[var] = choice(DUMMY_VALUES)
        except Exception as e:
            return jsonify(
                {"error": f"Error finding undeclared variables for dummy data: {e}"}
            ), 500
    else:
        if not values_string:
            return jsonify(
                {"error": "Values field cannot be empty when not using dummy data."}
            ), 400

        if input_type == "json":
            try:
                template_variables = json.loads(values_string)
            except json.JSONDecodeError as e:
                return jsonify(
                    {
                        "error": f"JSON decode error: {e}. Please ensure your JSON is valid."
                    }
                ), 400
            except TypeError as e:
                return jsonify(
                    {"error": f"Invalid JSON input type: {e}. Expected a string."}
                ), 400
        elif input_type == "yaml":
            try:
                # IMPORTANT: Use yaml.safe_load() for security.
                template_variables = yaml.safe_load(stream=values_string)
            except (yaml.YAMLError, TypeError) as e:
                return jsonify(
                    {
                        "error": f"YAML parse error: {e}. Please ensure your YAML is valid."
                    }
                ), 400
        else:
            return jsonify(
                {
                    "error": f"Undefined or unsupported input_type: '{escape(input_type)}'. Supported types are 'json' and 'yaml'."
                }
            ), 400

        if not isinstance(template_variables, dict):
            return jsonify(
                {
                    "error": f"Provided {input_type} data is not a dictionary. Template variables must be provided as a dictionary (e.g., {{'key': 'value'}})."
                }
            ), 400

    # 4. Jinja2 Template Rendering
    try:
        rendered_jinja2_tpl = jinja2_tpl.render(template_variables)
    except (exceptions.TemplateRuntimeError, ValueError, TypeError) as e:
        return jsonify(
            {
                "error": f"Error during template rendering: {e}. Check your template variables and their types."
            }
        ), 400
    except Exception as e:
        return jsonify(
            {"error": f"An unexpected error occurred during template rendering: {e}"}
        ), 500

    # 5. Post-processing: Replace whitespaces if requested
    if show_whitespaces:
        rendered_jinja2_tpl = rendered_jinja2_tpl.replace(" ", "•")

    # 6. Final Output Preparation
    # Escape final output for XSS prevention if inserted into HTML.
    final_output = escape(rendered_jinja2_tpl).replace("\n", "<br />")

    return jsonify({"rendered_output": final_output}), 200


if __name__ == "__main__":
    app.run(debug=True)
