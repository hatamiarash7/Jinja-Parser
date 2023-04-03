# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function

from flask import Flask, render_template, request
from jinja2 import Environment, meta, exceptions
from random import choice
from html import escape
import json
import yaml
from yaml import Loader


app = Flask(__name__)


@app.route("/")
def home():
    return render_template('index.html')


@app.route('/convert', methods=['GET', 'POST'])
def convert():
    jinja2_env = Environment()

    try:
        jinja2_tpl = jinja2_env.from_string(request.form['template'])
    except (exceptions.TemplateSyntaxError, exceptions.TemplateError) as e:
        return "Syntax error in jinja2 template: {0}".format(e)

    dummy_values = [
        'Lorem', 'Ipsum', 'Amet', 'Elit', 'Expositum',
        'Dissimile', 'Superiori', 'Laboro', 'Torquate', 'sunt',
    ]
    values = {}

    if bool(int(request.form['dummy'])):
        vars_to_fill = meta.find_undeclared_variables(
            jinja2_env.parse(request.form['template']))

        for v in vars_to_fill:
            values[v] = choice(dummy_values)
    else:
        if request.form['type'] == "json":
            try:
                values = json.loads(request.form['values'])
            except ValueError as e:
                return "Value error in JSON: {0}".format(e)

        elif request.form['type'] == "yaml":
            try:
                values = yaml.load(
                    stream=request.form['values'],
                    Loader=Loader
                )
            except (ValueError, yaml.parser.ParserError, TypeError) as e:
                return "Value error in YAML: {0}".format(e)
        else:
            return "Undefined input_type: {0}".format(request.form['type'])

    try:
        rendered_jinja2_tpl = jinja2_tpl.render(values)
    except (exceptions.TemplateRuntimeError, ValueError, TypeError) as e:
        return "Error in your values input filed: {0}".format(e)

    if bool(int(request.form['whitespaces'])):
        rendered_jinja2_tpl = rendered_jinja2_tpl.replace(' ', u'•')

    return escape(rendered_jinja2_tpl).replace('\n', '<br />')
