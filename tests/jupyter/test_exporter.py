import os
import pytest
import typing
import yaml

import mlrun.jupyter.exporter


class Constants(object):
    exporter_test_cases_file = "{}/exporter_cases.yml".format(os.path.dirname(__file__))


def cases_from_yml_file(file_path: str) -> typing.Generator[dict, None, None]:
    with open(file_path) as f:
        for case in yaml.load_all(f):
            yield pytest.param(case, id=case["name"])


@pytest.mark.parametrize(
    "case", cases_from_yml_file(Constants.exporter_test_cases_file)
)
@pytest.mark.parametrize("keyword", mlrun.jupyter.exporter.Constants.magic_keywords)
def test_convert_code(case: dict, keyword: str):
    notebook = {
        "cells": [
            {"source": code.format(keyword=keyword), "cell_type": "code"}
            for code in case["cells"]
        ],
    }
    exporter = mlrun.jupyter.exporter.MLRunExporter()
    code = exporter._convert_code(notebook)

    # Trim first line
    code = "\n".join(code.splitlines()[1:])
    assert code.strip() == case["expected"].strip()
