"""Safe YAML loading that also rejects silently overwritten mapping keys."""

import yaml
from yaml.constructor import ConstructorError


class UniqueKeyLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in mapping:
                raise ConstructorError(
                    None,
                    None,
                    "Expected unique string mapping keys",
                    key_node.start_mark,
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def load_yaml(content: str):
    return yaml.load(content, Loader=UniqueKeyLoader)
