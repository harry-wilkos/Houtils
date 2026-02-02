from collections import deque

import hdefereval
import hou

from ..utils.ui import default_node_color


class Auto_Color:
    def __init__(self, kwargs: dict):
        self.node = kwargs["node"]
        self.leader = self.calc_leader()
        if not kwargs["loading"]:
            hdefereval.executeDeferred(
                lambda: self.node.setCachedUserData(
                    "houtils:default_color", self.node.color()
                )
            )

        hdefereval.executeDeferred(
            lambda: (
                self.node.addEventCallback(
                    (
                        hou.nodeEventType.InputRewired,
                        hou.nodeEventType.InputDataChanged,
                    ),
                    self.parent_changed,
                ),
                self.node.addEventCallback(
                    (hou.nodeEventType.AppearanceChanged,),
                    self.color_changed,
                ),
            )
        )

        hdefereval.executeDeferred(self.parent_changed)

    def color_changed(self, event_type: hou.nodeEventType, **kwargs):
        if kwargs["change_type"] != hou.appearanceChangeType.Color:
            return

        # if not in edit mode change this
        self.node.setCachedUserData("houtils:auto", False)

        if self.check_in_out(self.node):
            for out in self.node.outputs():
                out.setCachedUserData("houtils:leader", True)
                out.setCachedUserData("houtils:auto", False)

        self.leader = self.calc_leader()
        self.flood_color()

        if self.check_default_color(self.node):
            self.node.setCachedUserData("houtils:auto", True)

    def parent_changed(self, event_type: hou.nodeEventType | None = None, **kwargs):
        self.leader = self.calc_leader()
        if self.leader:
            if not self.node.inputs() and self.node.cachedUserData("houtils:auto"):
                self.set_color(self.node, default_node_color(self.node))

            self.flood_color()
        elif leader := self.find_leader():
            color = leader.color()
            if self.check_default_color(leader, color):
                color = default_node_color(self.node)
            if not self.check_in_out(self.node):
                self.set_color(self.node, color)
            self.flood_color(color)

    def find_leader(self) -> hou.OpNode | None:
        queue = deque(self.node.inputs())
        store = set()
        container = self.node.parent()
        while queue:
            if (
                ((input := queue.popleft()) is None)
                or (input in store)
                or (input.parent() != container)
            ):
                continue
            if input.cachedUserData("houtils:leader"):
                return input

            parents = [
                input
                for input in input.inputs()
                if input is not None and input.parent() == container
            ]
            queue.extendleft(reversed(parents))
            store.add(input)

    def calc_leader(self) -> bool:
        color = self.node.color()
        default = self.check_default_color(self.node, color)
        container = self.node.parent()
        leader = False if self.check_in_out(self.node) else True

        queue = deque(self.node.inputs())
        store = set()
        while queue:
            if (
                ((input := queue.popleft()) is None)
                or (input in store)
                or (input.parent() != container)
            ):
                continue

            if not self.check_in_out(input) and (
                default
                or (color == input.color())
                or self.node.cachedUserData("houtils:auto")
            ):
                leader = False
                break

            parents = [
                input
                for input in input.inputs()
                if input is not None and input.parent() == container
            ]
            queue.extendleft(reversed(parents))
            store.add(input)

        return leader

    def flood_color(self, color: hou.Color | None = None):
        if self.check_in_out(self.node):
            return
        queue = deque(self.node.outputsWithIndices(True))
        store = set()
        color = self.node.color() if not color else color
        if self.check_default_color(self.node, color):
            color = None
        while queue:
            current = queue.pop()
            if (
                ((child := current[0]) is None)
                or (child in store)
                or (child.cachedUserData("houtils:leader"))
                or (current[2] != child.inputsWithIndices(True)[0][2])
                or (self.check_in_out(child))
            ):
                continue

            if not self.check_in_out(child):
                if not (apply_color := color):
                    apply_color = default_node_color(child)
                self.set_color(child, apply_color)
            queue.extend(child.outputsWithIndices(True))

    @staticmethod
    def check_in_out(node: hou.OpNode) -> bool:
        return (name := node.name()).startswith("OUT") or name.startswith("IN")

    @staticmethod
    def check_default_color(node: hou.OpNode, color: hou.Color | None = None) -> bool:
        color = node.color() if not color else color
        return default_node_color(node) == color

    @staticmethod
    def set_color(node: hou.OpNode, color: hou.Color):
        node.setColor(color)
        node.setCachedUserData("houtils:auto", True)

    @property
    def leader(self) -> bool:
        return self.node.cachedUserData("houtils:leader")

    @leader.setter
    def leader(self, state: bool):
        self.node.setCachedUserData("houtils:leader", state)
