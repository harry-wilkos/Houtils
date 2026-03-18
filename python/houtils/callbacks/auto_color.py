from collections import deque

import hdefereval
import hou
from houtils.utils.node import default_node_color, traverse_down, traverse_up

session = hou.session

key_auto = "houtils:auto"
key_leader = "houtils:leader"


class Auto_Color:
    def __init__(self, kwargs: dict):
        self.node = kwargs["node"]
        hdefereval.executeDeferred(lambda: self.deferred_init(kwargs["loading"]))

    def deferred_init(self, loading: bool):
        if not loading:
            self.node.setUserData(
                "houtils:default_color", " ".join(map(str, self.node.color().rgb()))
            )

        self.node.addEventCallback(
            (hou.nodeEventType.InputDataChanged, hou.nodeEventType.InputRewired),
            self.parent_changed,
        )
        self.node.addEventCallback(
            (hou.nodeEventType.AppearanceChanged,), self.color_changed
        )

        if not loading:
            if not session.houtils_auto_color and session.houtils_manual_color:
                self.node.setColor(session.houtils_manual_color)
            self.parent_changed()

    def color_changed(self, event_type: hou.nodeEventType, **kwargs):
        if kwargs["change_type"] != hou.appearanceChangeType.Color:
            return

        self.node.setUserData(key_auto, "0")
        if self.check_in_out(self.node):
            for out in self.node.outputs():
                out.setUserData(key_leader, "1")
                out.setUserData(key_auto, "0")

        leader = self.calc_leader()
        if not session.houtils_auto_color:
            if not self.leader and leader:
                self.node.setUserData(key_auto, "0")
                for out in self.node.outputs():
                    out.setUserData(key_leader, "1")
                    out.setUserData(key_auto, "0")
        else:
            self.flood_color()
        self.leader = leader

        if self.check_default_color(self.node):
            self.node.setUserData(key_auto, "1")
        elif not session.houtils_auto_color:
            session.houtils_manual_color = self.node.color()

    def parent_changed(self, event_type: hou.nodeEventType | None = None, **kwargs):
        leader = self.calc_leader()
        if not session.houtils_auto_color:
            if not self.leader and leader:
                self.node.setUserData(key_auto, "0")
            self.leader = leader
            return

        self.leader = leader
        if self.leader:
            if not self.node.inputs() and int(self.node.userData(key_auto) or False):
                self.set_color(self.node, default_node_color(self.node))
            self.flood_color()

        elif leader := self.find_leader():
            color = leader.color()
            if self.check_default_color(leader, color):
                color = default_node_color(self.node)
            if not self.check_in_out(self.node):
                self.set_color(self.node, color)
            self.flood_color(color)

    def calc_block(self) -> bool:
        block = False
        for node in traverse_up(self.node):
            print(node)
        return block

    def find_leader(self) -> hou.OpNode | None:
        for input in traverse_up(self.node):
            if int(input.userData(key_leader) or False):
                return input

    def calc_leader(self) -> bool:
        color = self.node.color()
        default = self.check_default_color(self.node, color)

        if self.check_in_out(self.node):
            return False

        leader = True
        is_auto = bool(int(self.node.userData(key_auto) or False))
        existing_leader = bool(int(self.node.userData(key_leader) or False))
        manual_color = session.houtils_manual_color

        for input in traverse_up(self.node):
            ignore = self.check_in_out(input)
            if not ignore and (default or (is_auto and session.houtils_auto_color)):
                leader = False
                break
            elif color == input.color():
                if color == manual_color:
                    leader = existing_leader
                else:
                    leader = False
                break
        return leader

    def flood_color(self, color: hou.Color | None = None):
        if self.check_in_out(self.node):
            return

        color = self.node.color() if not color else color
        if self.check_default_color(self.node, color):
            color = None

        for child in traverse_down(self.node):
            if (int(child.userData(key_leader) or False)) and (
                child.color() == color or (not color and default_node_color(child))
            ):
                child.setUserData(key_leader, "0")
                child.setUserData(key_auto, "1")
            elif self.check_in_out(child):
                continue

            final_color = color if color else default_node_color(child)
            self.set_color(child, final_color)

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
        node.setUserData(key_auto, "1")

    @property
    def leader(self) -> bool:
        return bool(int(self.node.userData(key_leader) or False))

    @leader.setter
    def leader(self, state: bool):
        self.node.setUserData(key_leader, str(int(state)))
