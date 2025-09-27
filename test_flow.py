from scalpel.cfg import CFGBuilder
from fno_convert.util.python.controlflow import PythonSequenceFactory
from fno_convert.util.python.controlflow import OrderFactory
from fno_convert.util.controlflow import Signature
from fno_convert.descriptors.python import PythonDescriptor
from fno_convert.graph import FnOGraph
import os


def get_source(path):
    with open(path, "r") as file:
        return file.read()


if __name__ == "__main__":
    path = "usecase/run.py"
    """name = "create_comp"

    src = get_source(path)

    cfgs = CFGBuilder().build_from_file(name, path, flattened=True)
    cfg = cfgs["mod." + name]

    order = OrderFactory.from_cfg(cfg)
    # print(order)

    seq = PythonSequenceFactory.from_order(order, cfg.name)
    sig = Signature.from_sequence(seq)
    # print(sig)"""

    g = FnOGraph()
    d = PythonDescriptor(g, os.getcwd())
    try:
        d.describe_file(path)
    except Exception as e:
        g.log()
        raise e

    g.serialize("usecase.ttl", format="turtle")
