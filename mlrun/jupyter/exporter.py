import base64
import os
import re
import typing
import yaml

import nbconvert.exporters
import nbconvert.filters
import nbformat

import mlrun.utils
import nuclio
import nuclio.utils


class Constants(object):
    magic_keywords = [
        "mlrun",
        "nuclio",
    ]


class Macros(type):
    comment = r"\s*#.*"
    macros = [
        "ignore",
        "start-code",
        "end-code",
    ]

    @classmethod
    def has_macro(mcs, macro: str, line: str) -> bool:
        if macro == "comment":
            return re.compile(mcs.comment).match(line) is not None
        if macro not in mcs.macros:
            raise AttributeError(macro)

        return (
            re.compile(
                fr"#\s*({'|'.join(Constants.magic_keywords)}):\s*{macro}"
            ).search(line)
            is not None
        )


class MLRunExporter(nbconvert.exporters.Exporter):

    # Add "File -> Download as" menu in the notebook
    export_from_notebook = "MLRun"

    @property
    def name(self):
        return f"{self.__module__}.{self.__class__.__name__}"

    @property
    def header(self):
        return f"# Generated by {self.name}\n"

    def from_notebook_node(
        self,
        nb: typing.Union[nbformat.NotebookNode, dict],
        resources: typing.Dict[str, str] = None,
        **kw: dict,
    ) -> (str, typing.Dict[str, str]):
        resources = resources or {}
        config = nuclio.config.new_config()
        name = mlrun.utils.get_in(resources, "metadata.name")
        if name:
            config["metadata"]["name"] = mlrun.utils.normalize_name(name)
        config["spec"]["handler"] = self._handler_name()

        code = self._convert_code(nb)

        if nuclio.utils.env_keys.code_target_path in os.environ:
            code_path = os.environ.get(nuclio.utils.env_keys.code_target_path)
            with open(code_path, "w") as fp:
                fp.write(code)
                fp.close()
        else:
            data = base64.b64encode(code.encode("utf-8")).decode("utf-8")
            mlrun.utils.update_in(config, "spec.build.functionSourceCode", data)

        yaml_config = self.header + yaml.dump(config, default_flow_style=False)
        resources["output_extension"] = ".yaml"

        return yaml_config, resources

    def _convert_code(self, nb: typing.Union[nbformat.NotebookNode, dict]) -> str:

        handler_path = os.environ.get(nuclio.utils.env_keys.handler_path)
        if handler_path:
            with open(handler_path) as fp:
                return fp.read()

        code = self.header
        for cell in filter(self._is_code_cell, nb["cells"]):
            cell_code = cell["source"]

            if Macros.has_macro("ignore", cell_code):
                continue

            if Macros.has_macro("end-code", cell_code):
                break

            if Macros.has_macro("start-code", cell_code):
                # if we see indication of start, we ignore all previous cells
                code = self.header

            cell_code = self._filter_comments(cell_code)
            if not cell_code.strip():
                continue

            cell_lines = cell_code.splitlines()
            code += self._handle_code_cell(cell_lines)

        return code

    @staticmethod
    def _handle_code_cell(cell_lines: typing.List[str]) -> str:
        processed_lines = []
        for line in cell_lines:
            if Macros.has_macro("comment", line):
                continue

            # ignore command or magic commands
            if not (line.startswith("!") or line.startswith("%")):
                processed_lines.append(line)

        if processed_lines:
            return nbconvert.filters.ipython2python("\n".join(processed_lines))

        return "\n"

    @staticmethod
    def _is_code_cell(cell: typing.Dict[str, str]) -> bool:
        return cell["cell_type"] == "code"

    def _handler_name(self) -> str:
        handler_path = os.environ.get(nuclio.utils.env_keys.handler_path)
        if handler_path:
            module = self._module_name(handler_path)
        else:
            module = "handler"

        name = os.environ.get(nuclio.utils.env_keys.handler_name, "handler")
        return "{}:{}".format(module, name)

    @staticmethod
    def _module_name(py_file: str) -> str:
        base = os.path.basename(py_file)
        module, _ = os.path.splitext(base)
        return module

    @staticmethod
    def _filter_comments(cell_code: str) -> str:
        lines = (
            line
            for line in cell_code.splitlines()
            if not Macros.has_macro("comment", line)
        )
        return "\n".join(lines)
