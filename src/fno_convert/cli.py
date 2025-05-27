import argparse
from .descriptors import Descriptor
from .graph import FnOGraph

def main():
    parser = argparse.ArgumentParser(
        prog="fno-convert",
        description="FnO Convert CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: describe
    describe_parser = subparsers.add_parser(
        "describe", help="Convert a resource into an FnO representation"
    )
    describe_parser.add_argument("resource", help="Input resource (e.g. JSON)")
    describe_parser.add_argument(
        "-o", "--output",
        default="output.ttl",
        help="Path to output TTL file (default: output.ttl)"
    )
    describe_parser.set_defaults(func=describe)

    # Subcommand: execute (not yet implemented)
    execute_parser = subparsers.add_parser(
        "execute", help="Execute a described FnO function (not implemented yet)"
    )
    execute_parser.set_defaults(func=execute)

    args = parser.parse_args()
    args.func(args)

def describe(args):
    g = FnOGraph()

    fno_rep = Descriptor.describe(g, args.resource)
    g.serialize(args.output, format="turtle")

    print(f"\nGenerated FnO Representation for {args.resource} in {args.output}:")

    for i, (fun_uri, map_uri, imp_uri) in enumerate(fno_rep):
        print(f"{i}:")
        print(f"\tFnO Function: \t{fun_uri}")
        print(f"\tFnO Mapping: \t{map_uri}")
        print(f"\tFnO Implementation: \t{imp_uri}")

def execute(args):
    g = FnOGraph()
    g.serialize(args.graph)

if __name__ == "__main__":
    main()