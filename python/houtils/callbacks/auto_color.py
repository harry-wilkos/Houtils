import re

import hdefereval
import hou
from houtils.utils.node import default_node_color, traverse_down, traverse_up

session = hou.session  # pyright: ignore[reportAttributeAccessIssue]
if match := re.search(r"^untitled.hip*", hou.hipFile.name()):
    hou.appendSessionModuleSource("houtils_auto_color = True")
elif not hasattr(session, "houtils_auto_color"):
    hou.appendSessionModuleSource("houtils_auto_color = False")
if not hasattr(session, "houtils_manual_color"):
    hou.appendSessionModuleSource("houtils_manual_color = None")

key_auto = "houtils:auto"
key_leader = "houtils:leader"
block_begins = frozenset(["compile_begin", "block_begin"])


class Node:
    def __init__(self, node: hou.OpNode):
        self.node = node

    def __getattr__(self, name):
        return getattr(self.node, name)

    def __eq__(self, other):
        if isinstance(other, Node):
            return self.node == other.node
        return self.node == other

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.node)

    def set_color(self, color: hou.Color):
        if self.node.color() != color:
            self.node.setColor(color)
        if self.node.userData(key_auto) != "1":
            self.node.setUserData(key_auto, "1")

    @property
    def leader(self) -> bool:
        return bool(int(self.node.userData(key_leader) or False))

    @leader.setter
    def leader(self, state: bool):
        val = str(int(state))
        if self.node.userData(key_leader) != val:
            self.node.setUserData(key_leader, val)


class Auto_Color:

    id_lookup = {}

    scheduling_lock = False
    processing_lock = False
    cycle_history = set()
    update_queue = []

    @classmethod
    def attach_callbacks(cls, kwargs: dict):
        node = kwargs["node"]
        cls.id_lookup[node.sessionId()] = node

        if kwargs.get("loading", False) or hou.hipFile.isLoadingHipFile():
            cls.init_node(node, load=False)
            node.addEventCallback(
                (hou.nodeEventType.InputRewired,), cls.parent_changed_entry
            )
            node.addEventCallback(
                (hou.nodeEventType.AppearanceChanged,), cls.color_changed_entry
            )
            node.addEventCallback((hou.nodeEventType.BeingDeleted,), cls.clean_up)
        else:
            hdefereval.executeDeferred(
                lambda: (
                    cls.init_node(node, load=True),
                    node.addEventCallback(
                        (hou.nodeEventType.InputRewired,), cls.parent_changed_entry
                    ),
                    node.addEventCallback(
                        (hou.nodeEventType.AppearanceChanged,), cls.color_changed_entry
                    ),
                    node.addEventCallback(
                        (hou.nodeEventType.BeingDeleted,), cls.clean_up
                    ),
                )
            )

    @classmethod
    def init_node(cls, raw_node: hou.OpNode, load: bool = True):
        node = Node(raw_node)

        default_color = None
        block_begin = raw_node.type().name() in block_begins
        block_end = (
            raw_node.node(str(raw_node.evalParm("blockpath"))) if block_begin else None
        )

        if block_begin and raw_node.inputs() and block_end:
            default_color = block_end.userData("houtils:default_color")

        if not default_color:
            default_color = " ".join(map(str, raw_node.color().rgb()))
            if block_begin and block_end:
                block_end.setUserData("houtils:default_color", default_color)

        if not raw_node.userData("houtils:default_color"):
            raw_node.setUserData("houtils:default_color", default_color)

        if raw_node.userData(key_auto) is None:
            raw_node.setUserData(
                key_auto, "1" if cls.check_default_color(raw_node) else "0"
            )

        if raw_node.userData(key_leader) is None:
            node.leader = cls.calc_leader(node)

        if not session.houtils_auto_color and (
            manual_color := session.houtils_manual_color
        ):
            node.set_color(manual_color)

        if load:
            cls.queue_event(raw_node.sessionId(), "parent")

    @classmethod
    def color_changed_entry(cls, event_type: hou.nodeEventType, **kwargs: dict):
        if (
            hou.hipFile.isLoadingHipFile()
            or kwargs["change_type"] != hou.appearanceChangeType.Color
            or cls.processing_lock
        ):
            return
        cls.queue_event(
            kwargs["node"].sessionId(),  # pyright: ignore[reportAttributeAccessIssue]
            "color",
        )

    @classmethod
    def parent_changed_entry(cls, event_type: hou.nodeEventType, **kwargs: dict):
        if hou.hipFile.isLoadingHipFile():
            return
        cls.queue_event(
            kwargs["node"].sessionId(),  # pyright: ignore[reportAttributeAccessIssue]
            "parent",
        )

    @classmethod
    def clean_up(cls, event_type: hou.nodeEventType, **kwargs: dict):

        if hou.hipFile.isShuttingDown():
            cls.id_lookup.clear()
            return
        try:
            id = kwargs[
                "node"
            ].sessionId()  # pyright: ignore[reportAttributeAccessIssue]
            if id in cls.id_lookup:
                del cls.id_lookup[id]
        except hou.ObjectWasDeleted:
            pass

    @classmethod
    def queue_event(cls, node_id: int, event_type: str):
        event = (node_id, event_type)
        if event not in cls.update_queue:
            cls.update_queue.append(event)

        if not cls.scheduling_lock:
            cls.scheduling_lock = True
            hdefereval.executeDeferred(cls.process_queue)

    @classmethod
    def process_queue(cls):
        cls.scheduling_lock = False
        cls.processing_lock = True
        with hou.undos.disabler():
            try:
                while cls.update_queue:
                    node_id, event_type = cls.update_queue.pop(0)
                    if node_id in cls.id_lookup:
                        try:
                            node = cls.id_lookup[node_id]
                            if event_type == "parent":
                                cls.parent_changed(node)
                            elif event_type == "color":
                                cls.color_changed(node)
                        except hou.ObjectWasDeleted:
                            pass
            finally:
                cls.cycle_history.clear()
                cls.processing_lock = False

    @classmethod
    def color_changed(cls, raw_node: hou.OpNode):
        node_id = raw_node.sessionId()
        if node_id in cls.cycle_history:
            return

        cls.cycle_history.add(node_id)
        node = Node(raw_node)

        block_begin = node.type().name() in block_begins

        if node.userData(key_auto) != "0":
            node.setUserData(key_auto, "0")

        if (in_out := cls.check_in_out(node)) and not cls.check_block(node):
            for out in node.outputs():
                if out.userData(key_leader) != "1":
                    out.setUserData(key_leader, "1")
                if out.userData(key_auto) != "0":
                    out.setUserData(key_auto, "0")

        leader = cls.calc_leader(node)

        if not session.houtils_auto_color:
            if not node.leader and leader:
                if node.userData(key_auto) != "0":
                    node.setUserData(key_auto, "0")
                for out in node.outputs():
                    if out.userData(key_leader) != "1":
                        out.setUserData(key_leader, "1")
                    if out.userData(key_auto) != "0":
                        out.setUserData(key_auto, "0")
        elif block_begin:
            cls.flood_color(node, force=True)
            cls.sync_block_siblings(node, force=True)
        else:
            cls.flood_color(node)

        node.leader = leader

        if cls.check_default_color(node):
            if node.userData(key_auto) != "1":
                node.setUserData(key_auto, "1")
        elif not session.houtils_auto_color and not in_out:
            session.houtils_manual_color = node.color()

    @classmethod
    def parent_changed(cls, raw_node: hou.OpNode):
        node_id = raw_node.sessionId()
        if node_id in cls.cycle_history:
            return

        cls.cycle_history.add(node_id)
        node = Node(raw_node)

        block_begin = node.type().name() in block_begins
        leader = cls.calc_leader(node)

        if not session.houtils_auto_color:
            if not node.leader and leader:
                if node.userData(key_auto) != "0":
                    node.setUserData(key_auto, "0")
            node.leader = leader
            return

        node.leader = leader

        if leader:
            if not node.inputs() and int(node.userData(key_auto) or False):
                color = default_node_color(node.node)
                if (
                    block_begin
                    and (block_end := node.node.node(node.evalParm("blockpath")))
                    and (leader_node := cls.find_leader(block_end, node.node))
                    and leader_node != node.node
                ):
                    leader_color = leader_node.color()
                    if cls.check_default_color(leader_node, leader_color):
                        color = default_node_color(node.node)
                    else:
                        color = leader_color
                node.set_color(color)
            cls.flood_color(node)

        elif leader_node := cls.find_leader(node.node, node.node):
            color = leader_node.color()
            if cls.check_default_color(leader_node, color):
                color = default_node_color(node.node)
            if not cls.check_in_out(node):
                node.set_color(color)
            cls.flood_color(node, color)
        else:
            if int(node.userData(key_auto) or False):
                color = default_node_color(node.node)
                if not cls.check_in_out(node):
                    node.set_color(color)
                cls.flood_color(node)

    @classmethod
    def find_leader(
        cls, target_node: hou.OpNode, fallback_node: hou.OpNode
    ) -> hou.OpNode | None:
        target = target_node if target_node else fallback_node
        for input_node, state in traverse_up(target):
            if int(input_node.userData(key_leader) or False):
                return input_node

    @classmethod
    def calc_leader(cls, node: Node) -> bool:
        color = node.color()
        default = cls.check_default_color(node, color)

        if cls.check_in_out(node) or cls.check_block(node):
            return False

        leader = True
        is_auto = node.userData(key_auto) == "1"
        existing_leader = node.leader
        manual_color = session.houtils_manual_color

        for input_node, state in traverse_up(node.node):
            ignore = cls.check_in_out(input_node)
            if not ignore and (default or (is_auto and session.houtils_auto_color)):
                leader = False
            elif color == input_node.color():
                if color == manual_color:
                    leader = existing_leader
                else:
                    leader = False
            elif ignore:
                continue
            break
        return leader

    @classmethod
    def flood_color(
        cls, node: Node, color: hou.Color | None = None, force: bool = False
    ):
        if cls.check_in_out(node):
            return

        color = node.color() if not color else color
        if cls.check_default_color(node, color):
            color = None

        for child, state in traverse_down(node.node):
            child_proxy = Node(child)

            if child_proxy.leader:
                if (child_color := child.color()) == color or (
                    not color and cls.check_default_color(child, child_color)
                ):
                    if child_proxy.leader:
                        child_proxy.leader = False
                    if child.userData(key_auto) != "1":
                        child.setUserData(key_auto, "1")
                else:
                    state.skip = True
                    continue
            elif cls.check_in_out(child):
                if not (force or cls.check_block(child)):
                    state.skip = True
                continue

            final_color = color if color else default_node_color(child)
            child_proxy.set_color(final_color)

            if child.type().name() in block_begins:
                cls.sync_block_siblings(child_proxy, final_color, force)

    @classmethod
    def sync_block_siblings(
        cls, node: Node, color: hou.Color | None = None, force: bool = False
    ):
        if node.type().name() not in block_begins:
            return

        if block_end := node.node.node(str(node.evalParm("blockpath"))):
            for b_node, b_state in traverse_up(block_end):
                if b_node.type().name() in block_begins:
                    b_state.skip = True
                    if b_node != node.node:
                        sib = Node(b_node)
                        if not cls.check_default_color(sib):
                            sib.leader = True
                        else:
                            sib.leader = False

                        target_color = color if color else sib.color()
                        cls.flood_color(sib, target_color, force)

    @staticmethod
    def check_block(node: hou.OpNode | Node) -> bool:
        raw_node = node.node if isinstance(node, Node) else node

        block = False
        store = set()
        for parent, state in traverse_up(raw_node):
            store.add(parent)
            if parent.type().name() in block_begins:
                block_end = parent.node(str(parent.evalParm("blockpath")))
                if not block_end:
                    continue
                if block_end not in store:
                    block = True
                    break
        return block

    @staticmethod
    def check_in_out(node: hou.OpNode | Node) -> bool:
        return node.name().startswith(("OUT", "IN"))

    @staticmethod
    def check_default_color(
        node: hou.OpNode | Node, color: hou.Color | None = None
    ) -> bool:
        raw_node = node.node if isinstance(node, Node) else node

        color = raw_node.color() if not color else color
        return default_node_color(raw_node) == color

