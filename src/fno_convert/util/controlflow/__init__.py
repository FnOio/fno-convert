from enum import Enum, auto
from typing import Optional
import ast


class SignatureType(Enum):
    FUNCTION = auto()
    ITER = auto()
    LOOP = auto()
    TEST = auto()
    BRANCH = auto()


class Signature:
    def __init__(self):
        self.id: Optional[str] = None
        self.type: Optional[SignatureType] = None
        self.inputs: dict[str, str] = {}
        self.assigns: set[str] = set()
        self.outputs: set[str] = set()
        self.stmts: list[ast.stmt] = []

        # FUNCTION
        self.seq: Optional["Sequence"] = None
        # LOOP
        self.iter: str = None
        # BRANCH
        self.branch: Optional["Branch"] = None
        self.test: str = None

    @staticmethod
    def from_sequence(seq: "Sequence") -> "Signature":
        sig = Signature()
        sig.id = seq.name
        if seq.id is not None:
            sig.id += f"_{seq.id}"
        sig.seq = seq
        sig.type = SignatureType.FUNCTION

        sig.inputs.update({var: "IN" for var in seq.inputs})
        sig.assigns.update(seq.inputs.intersection(seq.vars.keys()))
        sig.outputs.update(sig.assigns.copy())

        return sig

    @staticmethod
    def from_branch(branch: "Branch") -> "Signature":
        sig = Signature()
        sig.branch = branch

        sig.inputs.update({var: "IN" for var in branch.true_seq.inputs})
        sig.assigns.update(
            branch.true_seq.inputs.intersection(branch.true_seq.vars.keys())
        )
        if branch.false_seq:
            sig.inputs.update({var: "IN" for var in branch.false_seq.inputs})
            sig.assigns.update(
                branch.false_seq.inputs.intersection(branch.false_seq.vars.keys())
            )

        sig.type = SignatureType.BRANCH

        return sig

    def map(self, var, source):
        self.inputs[var] = source

    def to_string(self, indent: int = 0) -> str:
        pad = " " * indent
        parts = [
            f"{pad}Signature(id={self.id}, type={self.type.name if self.type else None})",
            f"{pad}  assigns: {sorted(self.assigns)}",
            f"{pad}  inputs: {self.inputs}",
            f"{pad}  outputs: {sorted(self.outputs)}",
        ]
        if self.seq:
            parts.append(f"{pad}  seq:")
            parts.append(self.seq.to_string(indent + 4))

        if self.branch:
            parts.append(f"{pad}  test: {self.test}")
            parts.append(f"{pad}  branch:")
            parts.append(self.branch.to_string(indent + 4))

        return "\n".join(parts)

    def __str__(self):
        return self.to_string()


class Sequence:
    def __init__(self):
        self.name: Optional[str] = None
        self.id: Optional[str] = None
        self.inputs: set[str] = set()
        self.vars: dict[str, str] = {}
        self.sigs: list[Signature] = []

    def add_signature(self, sig: "Signature"):
        for var in sig.inputs:
            if var in self.vars:
                sig.map(var, self.vars[var])
            else:
                self.inputs.add(var)

        for var in sig.assigns:
            self.vars[var] = sig.id

        self.sigs.append(sig)

    def calculate_outputs(self):
        used = set()

        for sig in reversed(self.sigs):
            for var in sig.assigns:
                if var in used or var in self.inputs:
                    sig.outputs.add(var)

            for var in sig.inputs:
                used.add(var)

    def to_string(self, indent: int = 0) -> str:
        pad = " " * indent
        parts = [f"{pad}Sequence(", f"{pad}  signatures:"]
        for sig in self.sigs:
            parts.append(sig.to_string(indent + 4))
        parts.append(f"{pad})")
        return "\n".join(parts)

    def __str__(self) -> str:
        return self.to_string()


class Loop(Sequence):

    def __init__(self):
        super().__init__()
        self.iter = iter


class Branch:

    def __init__(self):
        self.name: Optional[str] = None
        self.true_seq: Optional[Sequence] = None
        self.false_seq: Optional[Sequence] = None

    def to_string(self, indent: int = 0) -> str:
        pad = " " * indent
        lines = []

        if self.true_seq:
            lines.append(f"{pad}  True branch:")
            lines.append(self.true_seq.to_string(indent + 4))

        if self.false_seq:
            lines.append(f"{pad}  False branch:")
            lines.append(self.false_seq.to_string(indent + 4))

        return "\n".join(lines)
