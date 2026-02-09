from collections import deque

import hdefereval
import hou
from houtils.utils.ui import default_node_color

session = hou.session
key_auto = "houtils:auto"
key_leader = "houtils:leader"
key_default = "houtils:default_color"


class Auto_Color:
    def __init__(self, kwargs: dict):
        self.node = kwargs["node"]
        hdefereval.executeDeferred(lambda: self.deferred_init(kwargs["loading"]))

    def deferred_init(self, loading: bool):
        if not loading:
            self.node.setCachedUserData(key_default, self.node.color())

        self.node.addEventCallback(
            (hou.nodeEventType.InputDataChanged, hou.nodeEventType.InputRewired),
            self.parent_changed,
        )
        self.node.addEventCallback(
            (hou.nodeEventType.AppearanceChanged,), self.color_changed
        )

        if not loading:
            if not session.houtils_auto_color:
                self.node.setColor(session.houtils_manual_color)
            self.parent_changed()

    def color_changed(self, event_type: hou.nodeEventType, **kwargs):
        if kwargs["change_type"] != hou.appearanceChangeType.Color:
            return

        self.node.setCachedUserData(key_auto, False)
        if self.check_in_out(self.node):
            for out in self.node.outputs():
                out.setCachedUserData(key_leader, True)
                out.setCachedUserData(key_auto, False)

        leader = self.calc_leader()
        if not session.houtils_auto_color:
            if not self.leader and leader:
                self.node.setCachedUserData(key_auto, False)
                for out in self.node.outputs():
                    out.setCachedUserData(key_leader, True)
                    out.setCachedUserData(key_auto, False)
        else:
            self.flood_color()
        self.leader = leader

        if self.check_default_color(self.node):
            self.node.setCachedUserData(key_auto, True)
        elif not session.houtils_auto_color:
            session.houtils_manual_color = self.node.color()

    def parent_changed(self, event_type: hou.nodeEventType | None = None, **kwargs):
        leader = self.calc_leader()
        if not session.houtils_auto_color:
            if not self.leader and leader:
                self.node.setCachedUserData(key_auto, False)
            self.leader = leader
            return

        self.leader = leader
        if self.leader:
            if not self.node.inputs() and self.node.cachedUserData(key_auto):
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
            if input.cachedUserData(key_leader):
                return input

            parents = (
                inp
                for inp in reversed(input.inputs())
                if inp is not None and inp.parent() == container
            )

            queue.extendleft(parents)
            store.add(input)

    def calc_leader(self) -> bool:
        color = self.node.color()
        default = self.check_default_color(self.node, color)
        container = self.node.parent()

        if self.check_in_out(self.node):
            return False

        leader = True
        is_auto = self.node.cachedUserData(key_auto)

        queue = deque(self.node.inputs())
        store = set()
        while queue:
            if (
                ((input := queue.popleft()) is None)
                or (input in store)
                or (input.parent() != container)
            ):
                continue

            ignore = self.check_in_out(input)

            if not ignore and (
                default
                or (color == input.color())
                or (is_auto and session.houtils_auto_color)
            ):
                leader = False
                break

            store.add(input)
            if not ignore:
                continue

            parents = (
                inp
                for inp in reversed(input.inputs())
                if inp is not None and inp.parent() == container
            )

            queue.extendleft(parents)

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
                or (child.cachedUserData(key_leader))
                or (current[2] != child.inputsWithIndices(True)[0][2])
                or (self.check_in_out(child))
            ):
                continue

            final_color = color if color else default_node_color(child)
            self.set_color(child, final_color)
            queue.extend(child.outputsWithIndices(True))
            store.add(child)

    @staticmethod
    def check_in_out(node: hou.OpNode) -> bool:
        return node.name().startswith(("OUT", "IN"))

    @staticmethod
    def check_default_color(node: hou.OpNode, color: hou.Color | None = None) -> bool:
        color = node.color() if not color else color
        return default_node_color(node) == color

    @staticmethod
    def set_color(node: hou.OpNode, color: hou.Color):
        node.setColor(color)
        node.setCachedUserData(key_auto, True)

    @property
    def leader(self) -> bool:
        return self.node.cachedUserData(key_leader)

    @leader.setter
    def leader(self, state: bool):
        self.node.setCachedUserData(key_leader, state)
