from rdflib import URIRef, Literal, BNode
from enum import Enum, auto
from typing import Union, Optional

Mapping = Union["ValueMapping", "BranchMapping"]


class MappingStrategy(Enum):
    GET_ITEM = auto()
    SET_ITEM = auto()


class ValueMapping:
    def __init__(
        self,
        mapfrom: "MappingNode",
        mapto: "MappingNode",
        priority: URIRef | None = None,
    ) -> None:
        self.mapfrom = mapfrom
        self.mapto = mapto
        self.priority = priority

    def to_string(self, indent: int = 0) -> str:
        pad = " " * indent
        lines = [f"{pad}ValueMapping("]
        if self.mapfrom.from_for():
            lines.append(f"{pad}  for={self.mapfrom},")
        else:
            lines.append(f"{pad}  from={self.mapfrom},")
        lines.append(f"{pad}  to={self.mapto},")
        if self.priority:
            lines.append(f"{pad}  priority={self.priority},")
        lines.append(f"{pad})")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.to_string()


class BranchMapping:
    def __init__(
        self,
        mappings: list[Mapping],
        test: "MappingNode",
        test_value: bool,
        start: Optional[URIRef] = None,
    ):
        self.mappings = mappings
        self.test = test
        self.test_value = test_value
        self.start = start

    def to_string(self, indent: int = 0) -> str:
        pad = " " * indent
        lines = [f"{pad}CompositionMapping("]
        lines.append(f"{pad}  test={self.test},")

        # mapIf branch
        lines.append(f"{pad}  if=[")
        for mapping in self.mapIf:
            if hasattr(mapping, "_str"):
                lines.append(mapping.to_string(indent + 4))
            else:
                lines.append(" " * (indent + 4) + str(mapping))
        lines.append(f"{pad}  ],")

        # mapIfNot branch
        lines.append(f"{pad}  if not=[")
        for mapping in self.mapIfNot:
            if hasattr(mapping, "_str"):
                lines.append(mapping.to_string(indent + 4))
            else:
                lines.append(" " * (indent + 4) + str(mapping))
        lines.append(f"{pad}  ],")

        lines.append(f"{pad})")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.to_string()


from rdflib.term import URIRef, Literal, BNode


class MappingNode:
    def __init__(self) -> None:
        self.context = None
        self.parameter = None
        self.output = None
        self.key = None
        self.strategy = None
        self.constant = None
        self.iteration = False
        self.var = None

    def set_function_par(self, context, parameter) -> "MappingNode":
        self.context = context
        self.parameter = parameter
        self.output = None
        self.constant = None
        return self

    def set_function_out(self, context, output) -> "MappingNode":
        self.context = context
        self.output = output
        self.parameter = None
        self.constant = None
        return self

    def set_constant(self, constant) -> "MappingNode":
        if not isinstance(constant, (URIRef, Literal, BNode)):
            constant = Literal(constant)
        self.constant = constant
        self.context = None
        self.parameter = None
        self.output = None
        return self

    def set_iteration(self, iteration: bool = True) -> "MappingNode":
        self.iteration = iteration
        return self

    def get_value(self):
        if self.parameter is not None:
            return self.parameter
        if self.output is not None:
            return self.output
        return self.constant

    def set_strategy(self, strategy, key: int | str = None) -> "MappingNode":
        self.strategy = strategy
        self.key = key
        return self

    def is_output(self) -> bool:
        return self.output is not None

    def has_map_strategy(self) -> bool:
        return self.strategy is not None

    def from_term(self) -> bool:
        return self.parameter is None and self.output is None

    def from_for(self) -> bool:
        return self.iteration

    def from_variable(self, var: str) -> "MappingNode":
        self.var = var
        return self

    def to_string(self, indent: int = 0) -> str:
        pad = " " * indent
        details = []
        if self.parameter is not None:
            details.append(f"parameter={self.parameter}")
        if self.output is not None:
            details.append(f"output={self.output}")
        if self.constant is not None:
            details.append(f"constant={self.constant}")
        if self.context is not None:
            details.append(f"context={self.context}")
        if self.strategy is not None:
            details.append(f"strategy={self.strategy}")
        if self.key is not None:
            details.append(f"key={self.key}")
        if self.iteration:
            details.append("iteration=True")
        if self.var is not None:
            details.append(f"var={self.var}")

        return f"{pad}MappingNode({', '.join(details) if details else 'empty'})"

    def __str__(self) -> str:
        return self.to_string()
