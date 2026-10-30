"""Load backend/template.yaml for tests, with CloudFormation's short-form tags.

A plain YAML loader refuses `!Ref` and its kin, so this one turns each tag into
the long form CloudFormation itself reads: `!Ref X` into {"Ref": "X"},
`!GetAtt A.B` into {"Fn::GetAtt": ["A", "B"]} and any other `!Name v` into
{"Fn::Name": v}. Comments don't survive parsing, so `raw_lines` gives the file's
lines for the tests that check them.
"""

from pathlib import Path

import yaml

TEMPLATE = Path(__file__).resolve().parents[1] / "template.yaml"


class _CfnLoader(yaml.SafeLoader):
    """SafeLoader plus CloudFormation's tags; registering here leaves SafeLoader as it is."""


def _construct_tag(loader: yaml.SafeLoader, suffix: str, node: yaml.Node) -> dict:
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)
    if suffix == "Ref":
        return {"Ref": value}
    if suffix == "GetAtt" and isinstance(value, str):
        return {"Fn::GetAtt": value.split(".", 1)}
    return {f"Fn::{suffix}": value}


_CfnLoader.add_multi_constructor("!", _construct_tag)


def load_template(path: Path = TEMPLATE) -> dict:
    with path.open(encoding="utf-8") as stream:
        # A SafeLoader subclass, so `!!python/...` tags still raise.
        return yaml.load(stream, Loader=_CfnLoader)


def raw_lines(path: Path = TEMPLATE) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()
