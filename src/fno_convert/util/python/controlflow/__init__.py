from scalpel.cfg.model import Block, CFG
from ..ast import analyze_statements, analyze_for_statement, analyze_if_statement
from ...controlflow import Signature, SignatureType, Sequence, Branch
from typing import List
from .order import LinOrder, LoopOrder, ConditionalOrder, OrderFactory
import ast


class PythonSignatureFactory:

    @staticmethod
    def from_block(id: str, name: str, stmts: List[ast.stmt]) -> Signature:
        sig = Signature()
        sig.id = f"{name}_{id}"
        sig.assigns, inputs = analyze_statements(stmts)
        sig.inputs = {var: "IN" for var in inputs}
        sig.stmts = stmts
        sig.type = SignatureType.FUNCTION
        return sig

    @staticmethod
    def from_for(id: str, name: str, stmt: ast.For) -> Signature:
        sig = Signature()
        sig.id = f"{name}_iter_{id}"
        sig.assigns, used = analyze_for_statement(stmt)
        sig.inputs = {input: "IN" for input in used}
        sig.outputs = sig.assigns.copy()
        sig.stmts = [stmt]
        sig.type = SignatureType.ITER
        return sig

    @staticmethod
    def from_loop(seq: Sequence, iter: Signature) -> Signature:
        sig = Signature.from_sequence(seq)
        sig.id = iter.id.replace("iter", "loop")
        sig.inputs.update({var: "IN" for var in iter.assigns})
        sig.iter = iter.id
        sig.type = SignatureType.LOOP
        return sig

    @staticmethod
    def from_if(id: str, name: str, stmt: ast.If) -> Signature:
        sig = Signature()
        sig.id = f"{name}_test_{id}"
        sig.inputs = {var: "IN" for var in analyze_if_statement(stmt)}
        sig.stmts = [stmt]
        sig.type = SignatureType.TEST
        return sig

    @staticmethod
    def from_branch(branch: Branch, test: Signature) -> Signature:
        sig = Signature.from_branch(branch)
        sig.id = test.id.replace("test", "branch")
        sig.test = test.id
        sig.type = SignatureType.BRANCH
        return sig


class PythonSequenceFactory:
    @staticmethod
    def from_cfg(cfg: CFG) -> Sequence:
        order = OrderFactory.from_cfg(cfg)
        return PythonSequenceFactory.from_order(order, cfg.name)

    @staticmethod
    def from_comp(comp, name: str):
        order = OrderFactory.from_comp(comp, name)
        return PythonSequenceFactory.from_order(order, name)

    @staticmethod
    def from_order(order: LinOrder, name: str) -> Sequence:
        seq = Sequence()
        seq.name = name
        if order.id is not None:
            seq.id = order.id

        for el in order:
            if isinstance(el, Block):
                PythonSequenceFactory._handle_block(seq, el)
            elif isinstance(el, LoopOrder):
                PythonSequenceFactory._handle_loop(seq, el)
            else:
                PythonSequenceFactory._handle_cond(seq, el)

        seq.calculate_outputs()
        return seq

    @staticmethod
    def _handle_loop(seq: Sequence, loop_order: LoopOrder):
        iter = loop_order.iter
        if len(iter.statements) > 1:
            sig = PythonSignatureFactory.from_block(
                iter.id, seq.name, iter.statements[:-1]
            )
            seq.add_signature(sig)

        # Create signature for the iterator
        stmt = iter.statements[-1]
        iter_sig = PythonSignatureFactory.from_for(iter.id, seq.name, stmt)
        seq.add_signature(iter_sig)
        # Create signature for the body
        loop_seq = PythonSequenceFactory.from_order(loop_order.loop, seq.name)
        loop_sig = PythonSignatureFactory.from_loop(loop_seq, iter_sig)
        seq.add_signature(loop_sig)

    @staticmethod
    def _handle_cond(seq: Sequence, cond_order: ConditionalOrder):
        test = cond_order.test
        if len(test.statements) > 1:
            sig = PythonSignatureFactory.from_block(
                test.id, seq.name, test.statements[:-1]
            )
            seq.add_signature(sig)

        # Create signature for the test
        stmt = test.statements[-1]
        test_sig = PythonSignatureFactory.from_if(test.id, seq.name, stmt)
        seq.add_signature(test_sig)
        # Create branch
        branch = PythonBranchFactory.from_branches(
            cond_order.true_branch, cond_order.false_branch, seq.name
        )
        # Create branch signature
        branch_sig = PythonSignatureFactory.from_branch(branch, test_sig)
        seq.add_signature(branch_sig)

    @staticmethod
    def _handle_block(seq: Sequence, block: Block):
        sig = PythonSignatureFactory.from_block(block.id, seq.name, block.statements)
        seq.add_signature(sig)


class PythonBranchFactory:

    @staticmethod
    def from_branches(true_branch: LinOrder, false_branch: LinOrder, name: str):
        branch = Branch()

        branch.true_seq = PythonSequenceFactory.from_order(true_branch, name)
        if false_branch:
            branch.false_seq = PythonSequenceFactory.from_order(false_branch, name)

        return branch
