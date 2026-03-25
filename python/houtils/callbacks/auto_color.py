import hdefereval
import hou
from houtils.utils.node import default_node_color, traverse_down, traverse_up

session = hou.session

key_auto = "houtils:auto"
key_leader = "houtils:leader"
block_begins = frozenset(["compile_begin", "block_begin"])


class Auto_Color_Manager:
    cache = {}

    @classmethod
    def color_changed_entry(cls, event_type: hou.nodeEventType, **kwargs: dict):
        if kwargs["change_type"] != hou.appearanceChangeType.Color:
            return
        try:
            id = kwargs["node"].sessionId()
            if id not in cls.cache:
                cls.cache[id] = Auto_Color(kwargs)
            cls.cache[id].color_changed()
        except hou.ObjectWasDeleted:
            pass

    @classmethod
    def parent_changed_entry(cls, event_type: hou.nodeEventType, **kwargs: dict):
        try:
            id = kwargs["node"].sessionId()
            if id not in cls.cache:
                cls.cache[id] = Auto_Color(kwargs)
            cls.cache[id].parent_changed()
        except hou.ObjectWasDeleted:
            pass

    @classmethod
    def clean_up(cls, event_type: hou.nodeEventType, **kwargs: dict):
        if hou.hipFile.isShuttingDown():
            cls.cache.clear()
            return
        try:
            id = kwargs["node"].sessionId()
            if id in cls.cache:
                del cls.cache[id]
        except hou.ObjectWasDeleted:
            pass

    @classmethod
    def attach_callbacks(cls, kwargs: dict):
        node = kwargs["node"]

        node.addEventCallback(
            (hou.nodeEventType.BeingDeleted,),
            cls.clean_up,
        )

        if kwargs["loading"]:
            node.addEventCallback(
                (hou.nodeEventType.InputDataChanged, hou.nodeEventType.InputRewired),
                cls.parent_changed_entry,
            )
            node.addEventCallback(
                (hou.nodeEventType.AppearanceChanged,),
                cls.color_changed_entry,
            )
        else:
            instance = Auto_Color(kwargs)
            cls.cache[node.sessionId()] = instance
            hdefereval.executeDeferred(
                lambda: (
                    instance.deferred_init(),
                    node.addEventCallback(
                        (
                            hou.nodeEventType.InputDataChanged,
                            hou.nodeEventType.InputRewired,
                        ),
                        cls.parent_changed_entry,
                    ),
                    node.addEventCallback(
                        (hou.nodeEventType.AppearanceChanged,),
                        cls.color_changed_entry,
                    ),
                )
            )


class Auto_Color:
    depth = 0
    history = set()

    def __init__(self, kwargs: dict):
        self.node = kwargs["node"]
        self.id = self.node.sessionId()
        self.block_begin = self.node.type().name() in block_begins

    def deferred_init(self):
        if self.block_begin and (
            block_end := self.node.node(self.node.evalParm("blockpath"))
        ):
            default_color = block_end.userData("houtils:default_color")
        else:
            default_color = " ".join(map(str, self.node.color().rgb()))

        if self.node.userData("houtils:default_color") != default_color:
            self.node.setUserData("houtils:default_color", default_color)
        if not session.houtils_auto_color and session.houtils_manual_color:
            self.set_color(self.node, session.houtils_manual_color)
        self.parent_changed()

    def color_changed(self):
        if self.id in Auto_Color.history:
            return

        Auto_Color.depth += 1
        Auto_Color.history.add(self.id)

        try:
            if self.node.userData(key_auto) != "0":
                self.node.setUserData(key_auto, "0")

            if self.check_in_out(self.node) and not self.check_block(self.node):
                for out in self.node.outputs():
                    if out.userData(key_leader) != "1":
                        out.setUserData(key_leader, "1")
                    if out.userData(key_auto) != "0":
                        out.setUserData(key_auto, "0")

            leader = self.calc_leader()
            if not session.houtils_auto_color:
                if not self.leader and leader:
                    if self.node.userData(key_auto) != "0":
                        self.node.setUserData(key_auto, "0")
                    for out in self.node.outputs():
                        if out.userData(key_leader) != "1":
                            out.setUserData(key_leader, "1")
                        if out.userData(key_auto) != "0":
                            out.setUserData(key_auto, "0")
            elif self.block_begin:
                self.flood_color(force=True)
            else:
                self.flood_color()

            self.leader = leader

            if self.check_default_color(self.node):
                if self.node.userData(key_auto) != "1":
                    self.node.setUserData(key_auto, "1")
            elif not session.houtils_auto_color:
                session.houtils_manual_color = self.node.color()

        finally:
            Auto_Color.depth -= 1
            if Auto_Color.depth == 0:
                Auto_Color.history.clear()

    def parent_changed(self):
        if self.id in Auto_Color.history:
            return

        Auto_Color.depth += 1
        Auto_Color.history.add(self.id)

        try:
            leader = self.calc_leader()

            if not session.houtils_auto_color:
                if not self.leader and leader:
                    if self.node.userData(key_auto) != "0":
                        self.node.setUserData(key_auto, "0")
                self.leader = leader
                return

            self.leader = leader
            if leader:
                if not self.node.inputs() and int(
                    self.node.userData(key_auto) or False
                ):
                    color = default_node_color(self.node)
                    if (
                        self.block_begin
                        and (
                            block_end := self.node.node(self.node.evalParm("blockpath"))
                        )
                        and (leader_node := self.find_leader(block_end))
                        and leader_node != self.node
                    ):
                        leader_color = leader_node.color()
                        if self.check_default_color(leader_node, leader_color):
                            color = default_node_color(self.node)
                        else:
                            color = leader_color
                    self.set_color(self.node, color)
                self.flood_color()
            elif leader_node := self.find_leader():
                color = leader_node.color()
                if self.check_default_color(leader_node, color):
                    color = default_node_color(self.node)
                if not self.check_in_out(self.node):
                    self.set_color(self.node, color)
                self.flood_color(color)
        finally:
            Auto_Color.depth -= 1
            if Auto_Color.depth == 0:
                Auto_Color.history.clear()

    def find_leader(self, node: hou.OpNode | None = None) -> hou.OpNode | None:
        node = node if node else self.node
        for input, state in traverse_up(node):
            if int(input.userData(key_leader) or False):
                return input

    def calc_leader(self) -> bool:
        color = self.node.color()
        default = self.check_default_color(self.node, color)

        if self.check_in_out(self.node) or self.check_block(self.node):
            return False

        leader = True
        is_auto = self.node.userData(key_auto) == "1"
        existing_leader = self.node.userData(key_leader) == "1"
        manual_color = session.houtils_manual_color

        for input, state in traverse_up(self.node):
            ignore = self.check_in_out(input)
            if not ignore and (default or (is_auto and session.houtils_auto_color)):
                leader = False
                # break
            elif color == input.color():
                if color == manual_color:
                    leader = existing_leader
                else:
                    leader = False
                # break
            # if not ignore:

            # state.skip = True
            break
        return leader

    def flood_color(self, color: hou.Color | None = None, force: bool = False):
        if self.check_in_out(self.node):
            return
        color = self.node.color() if not color else color
        if self.check_default_color(self.node, color):
            color = None

        for child, state in traverse_down(self.node):
            if child.userData(key_leader) == "1":
                if (child_color := child.color()) == color or (
                    not color and self.check_default_color(child, child_color)
                ):
                    if child.userData(key_leader) != "0":
                        child.setUserData(key_leader, "0")
                    if child.userData(key_auto) != "1":
                        child.setUserData(key_auto, "1")
                else:
                    state.skip = True
                    continue
            elif self.check_in_out(child):
                if not (force or self.check_block(child)):
                    state.skip = True
                continue

            final_color = color if color else default_node_color(child)
            self.set_color(child, final_color)

    @staticmethod
    def check_block(node: hou.OpNode) -> bool:
        block = False
        store = set()
        for parent, state in traverse_up(node):
            store.add(parent)
            if parent.type().name() in block_begins:
                block_end = parent.node(parent.evalParm("blockpath"))
                if not block_end:
                    continue
                if not block_end in store:
                    block = True
                    break
        return block

    @staticmethod
    def check_in_out(node: hou.OpNode) -> bool:
        return node.name().startswith(("OUT", "IN"))

    @staticmethod
    def check_default_color(node: hou.OpNode, color: hou.Color | None = None) -> bool:
        color = node.color() if not color else color
        return default_node_color(node) == color

    @staticmethod
    def set_color(node: hou.OpNode, color: hou.Color):
        if node.color() != color:
            node.setColor(color)
        if node.userData(key_auto) != "1":
            node.setUserData(key_auto, "1")

    @property
    def leader(self) -> bool:
        return bool(int(self.node.userData(key_leader) or False))

    @leader.setter
    def leader(self, state: bool):
        val = str(int(state))
        if self.node.userData(key_leader) != val:
            self.node.setUserData(key_leader, val)
