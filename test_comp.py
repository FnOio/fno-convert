from scalpel.cfg import CFGBuilder
from fno_convert.util.python.controlflow import PythonSequenceFactory
from fno_convert.util.python.controlflow import OrderFactory
from fno_convert.util.controlflow import Signature
from fno_convert.descriptors.python import PythonDescriptor
from fno_convert.graph import FnOGraph
from fno_convert.util.python.rewrite import ASTRewriter
import ast
import os


def get_source(path):
    with open(path, "r") as file:
        return file.read()


if __name__ == "__main__":
    path = "py_examples/comprehension.py"
    name = "create_comp"

    mod = ast.parse("[ord(c) for line in file for c in line if len(line) > 2]")
    comp = mod.body[0].value

    seq = PythonSequenceFactory.from_comp(comp, "listcomp")
    sig = Signature.from_sequence(seq)
    print(sig)

    """g = FnOGraph()
    d = PythonDescriptor(g, os.getcwd())
    try:
        d.describe_file(path)
    except Exception as e:
        g.log()
        raise e

    g.serialize("test_flow.ttl", format="turtle")"""
