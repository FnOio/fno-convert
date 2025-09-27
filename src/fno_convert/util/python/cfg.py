from scalpel.cfg.model import Block
from typing import List


def get_for_body(for_block: Block) -> List[Block]:
    body = []
    blocks = [exit.target for exit in for_block.exits if exit.exitcase]
    block = blocks.pop()

    while block:
        body.append(block)

        for exit in block.exits:
            if exit.target != for_block:
                blocks.append(exit.target)

        try:
            block = blocks.pop()
        except IndexError:
            block = None

    return body
