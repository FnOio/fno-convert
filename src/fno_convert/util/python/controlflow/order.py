from collections import deque
from scalpel.cfg.model import Block, CFG, Link
from scalpel.cfg import CFGBuilder
from typing import Optional, Union, List, Tuple, Set
from ..rewrite import ASTRewriter
import ast

OrderElement = Union["Block", "LoopOrder", "ConditionalOrder"]


class LinOrder:
    """Represents a linear order of order elements"""

    def __init__(self):
        self.id: Optional[str] = None
        self.list: List[OrderElement] = []

    def __iter__(self):
        """Iterate over order elements"""
        return iter(self.list)

    def __bool__(self):
        return bool(self.list)

    def __repr__(self):
        return self.to_string()

    def append(self, el: OrderElement):
        self.list.append(el)

    def to_string(self, indent: int = 0) -> str:
        pad = "  " * indent
        lines = []
        for el in self:
            if isinstance(el, (LoopOrder, ConditionalOrder)):
                lines.append(el.to_string(indent))
            else:
                lines.append(f"{pad}Block(id={el.id})")
        return "\n".join(lines)


class LoopOrder:
    """Represents a loop (e.g., for-loop) with its iteration block and body."""

    def __init__(self, iter_block: Block = None):
        self.iter: Block = iter_block
        self.loop: LinOrder = LinOrder()

    def to_string(self, indent: int = 0) -> str:
        pad = "  " * indent
        header = f"{pad}Loop(iter=Block(id={self.iter.id}))"
        body = self.loop.to_string(indent + 1)
        return f"{header}\n{body}"

    def __repr__(self):
        return self.to_string()


class ConditionalOrder:
    """Represents a conditional block with true/false branches."""

    def __init__(self, test_block: Block = None):
        self.test: Block = test_block
        self.true_branch: LinOrder = LinOrder()
        self.false_branch: LinOrder = LinOrder()

    def to_string(self, indent: int = 0) -> str:
        pad = "  " * indent
        lines = [f"{pad}If(test=Block(id={self.test.id})):"]
        lines.append(f"{pad}  True branch:")
        lines.append(self.true_branch.to_string(indent + 2))
        lines.append(f"{pad}  False branch:")
        lines.append(self.false_branch.to_string(indent + 2))
        return "\n".join(lines)

    def __repr__(self):
        return self.to_string()


class OrderFactory:

    @staticmethod
    def from_cfg(cfg: "CFG"):
        block = cfg.entryblock
        order: LinOrder = LinOrder()
        return OrderFactory.visit_block(order, block)

    @staticmethod
    def from_comp(comp_node, name: str):
        """
        Convert an ast.ListComp node into a CFG and generate its order.
        """
        """
        Rewrite a comprehension (list or dict) as a loop with explicit appending.
        """
        cfg = CFGBuilder().build(name, rewrite_comprehension(comp_node))
        dot = cfg.build_visual("png")
        dot.render(f"cfg_diagrams/{name}_cfg_diagram")
        return OrderFactory.from_cfg(cfg)

    @staticmethod
    def visit_block(
        order: LinOrder,
        block: "Block",
        visited: Set[Block] = set(),
        constrain: Optional[Set[Block]] = None,
    ):
        """
        Recursively walk the CFG and build an order
        """
        if constrain and block not in constrain:
            return order
        if block in visited:
            return order
        visited.add(block)

        # terminal block
        if len(block.exits) == 0:
            order.append(block)
            return order

        # straight-line code
        if len(block.exits) == 1 and not isinstance(
            block.statements[-1], (ast.If, ast.For)
        ):
            order.append(block)
            return OrderFactory.visit_block(
                order, block.exits[0].target, visited, constrain
            )

        # conditional
        if isinstance(block.statements[-1], ast.If):
            cond = ConditionalOrder()
            cond.test = block
            order.append(cond)

            true_branch, false_branch, merge_block = branch_blocks(block)

            # prepare constraint sets once
            true_set = set(true_branch)
            false_set = set(false_branch)

            # recurse into each branch
            if true_branch:
                cond.true_branch.id = true_branch[0].id
                for b in true_branch:
                    OrderFactory.visit_block(cond.true_branch, b, visited, true_set)

            if false_branch:
                cond.false_branch.id = false_branch[0].id
                for b in false_branch:
                    OrderFactory.visit_block(cond.false_branch, b, visited, false_set)

            # continue after merge
            if merge_block and (constrain is None or merge_block in constrain):
                return OrderFactory.visit_block(order, merge_block, visited)
            return order

        # loop
        if isinstance(block.statements[-1], ast.For):
            loop_order = LoopOrder()
            loop_order.iter = block
            order.append(loop_order)

            # detect backedge (the exit with exitcase set is loop body start)
            entry = loop_entry(block)
            # recurse into loop body
            OrderFactory.visit_block(loop_order.loop, entry, visited, constrain)

            # continue with exit that is not the loop body
            exit = loop_exit(block)
            return OrderFactory.visit_block(order, exit, visited, constrain)

        # fallback: just append and stop
        order.append(block)
        return order


def loop_entry(block: Block) -> Block:
    for exit in block.exits:
        if exit.exitcase is not None:
            return exit.target
    raise ValueError("No link found with an exitcase")


def loop_exit(block: Block) -> Block:
    for exit in block.exits:
        if exit.exitcase is None:
            return exit.target
    raise ValueError("No link found without an exitcase")


def collect_until_merge(start: "Block", merge: Optional["Block"]) -> List["Block"]:
    """
    Collect blocks in BFS order from `start` until hitting `merge`.
    The merge block itself is excluded and not enqueued.
    """
    visited = set()
    queue = deque([start])
    branch: List["Block"] = []

    while queue:
        block = queue.popleft()
        if block in visited or (merge and block.id == merge.id):
            continue
        visited.add(block)
        branch.append(block)

        for exit in block.exits:
            if merge is None or exit.target.id != merge.id:
                queue.append(exit.target)

    return branch


def find_first_merge(true_start: "Block", false_start: "Block") -> Optional["Block"]:
    """
    BFS from both starts, return the first common block (merge).
    """
    true_queue, false_queue = deque([true_start]), deque([false_start])
    true_seen, false_seen = {true_start}, {false_start}

    while true_queue or false_queue:
        if true_queue:
            b = true_queue.popleft()
            if b in false_seen:
                return b
            for exit in b.exits:
                if exit.target not in true_seen:
                    true_seen.add(exit.target)
                    true_queue.append(exit.target)

        if false_queue:
            b = false_queue.popleft()
            if b in true_seen:
                return b
            for exit in b.exits:
                if exit.target not in false_seen:
                    false_seen.add(exit.target)
                    false_queue.append(exit.target)

    return None


def branch_blocks(
    condition: "Block",
) -> Tuple[List["Block"], List["Block"], Optional["Block"]]:
    """
    Given a conditional block, return (true_branch_blocks, false_branch_blocks, merge_block).
    Assumes the last statement in `condition` is an AST If node.
    """
    if len(condition.exits) != 2:
        raise ValueError("Not a conditional block (should have 2 successors).")

    true_block, false_block = (exit.target for exit in condition.exits)
    if true_block == false_block:
        block = Block(condition.id)
        if_stmt = condition.statements[0]
        block.statements = if_stmt.body
        return [block], [], true_block

    # Find earliest merge block
    merge_block = find_first_merge(true_block, false_block)

    # Collect BFS order blocks for each branch, excluding the merge
    true_branch = collect_until_merge(true_block, merge_block)
    false_branch = collect_until_merge(false_block, merge_block)

    return true_branch, false_branch, merge_block


def rewrite_comprehension(comp_node):
    # Create a new list (or dict for DictComp)
    if isinstance(comp_node, ast.ListComp):
        init_value = ast.List(elts=[], ctx=ast.Load())
        append_method = "append"
    elif isinstance(comp_node, ast.DictComp):
        init_value = ast.Dict(keys=[], values=[])
        append_method = None  # No append method; use key-value assignment
    elif isinstance(comp_node, ast.SetComp):
        init_value = ast.Set(elts=[])
        append_method = "add"
    else:
        raise ValueError("Unsupported comprehension type")

    # Create the assignment: `target = []` or `target = {}`
    container_store = ast.Name("_", ast.Store())
    container_load = ast.Name("_", ast.Load())
    assign_init = ast.Assign(targets=[container_store], value=init_value)

    if isinstance(comp_node, (ast.ListComp, ast.SetComp)):
        body_stmt = ast.Call(
            func=ast.Attribute(
                value=container_load,
                attr=append_method,
                ctx=ast.Load(),
            ),
            args=[comp_node.elt],
            keywords=[],
        )
    else:
        body_stmt = ast.Assign(
            targets=[
                ast.Subscript(
                    value=container_load,
                    slice=comp_node.key,
                    ctx=ast.Store(),
                )
            ],
            value=comp_node.value,
        )

    for generator in reversed(comp_node.generators):
        for test in generator.ifs:
            body_stmt = ast.If(test=test, body=[body_stmt], orelse=[])
        body_stmt = ast.For(
            target=generator.target, iter=generator.iter, body=[body_stmt], orelse=[]
        )

    ret_stmt = ast.Return(container_load)

    body = ast.Module(body=[assign_init, body_stmt, ret_stmt])
    ast.fix_missing_locations(body)
    return body
