from collections import deque
from typing import Iterator

import hou


def default_node_color(node: hou.OpNode) -> hou.Color:
    if stored_color := node.userData("houtils:default_color"):
        color = hou.Color(tuple(map(float, stored_color.split())))
    else:
        color = node.type().defaultColor()
    return color


def traverse_up(node: hou.OpNode) -> Iterator[hou.OpNode]:
    queue = deque(node.inputs())
    store = set()
    container = node.parent()
    while queue:
        if (
            ((input := queue.popleft()) is None)
            or (input in store)
            or (input.parent() != container)
        ):
            continue
        yield input
        parents = (
            inp
            for inp in reversed(input.inputs())
            if inp is not None and inp.parent() == container
        )

        queue.extendleft(parents)
        store.add(input)


def traverse_down(node: hou.OpNode) -> Iterator[hou.OpNode]:
    queue = deque(node.outputsWithIndices(True))
    store = set()
    while queue:
        current = queue.pop()
        if (
            ((child := current[0]) is None)
            or (child in store)
            or (current[2] != child.inputsWithIndices(True)[0][2])
        ):
            continue
        yield child
        queue.extend(child.outputsWithIndices(True))
        store.add(child)
