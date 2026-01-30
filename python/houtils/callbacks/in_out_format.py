import hou
from ..utils.ui import default_node_color


class In_Out_Format:
    out_state = (hou.Color(1, 1, 1), "bulge")
    in_state = (hou.Color(1, 1, 1), "bulge_down")

    def __init__(self, kwargs: dict):
        self.node = kwargs["node"]
        self.type = self.node.type()
        self.node.addEventCallback((hou.nodeEventType.NameChanged,), self.format)

        current_state = (
            self.node.color(),
            self.node.userData("nodeshape") or self.node.type().defaultShape(),
        )

        if current_state in (self.out_state, self.in_state):
            node_type = self.node.type()
            self.state = (node_type.defaultColor(), node_type.defaultShape())
            self._state_saved = True
        else:
            self.state = current_state
            self._state_saved = False

    def format(
        self,
        event_type: hou.nodeEventType,  # pyright: ignore[reportUnusedParameter]
        **kwargs: hou.OpNode,
    ):
        pre_state = (
            self.node.color(),
            self.node.userData("nodeshape") or self.node.type().defaultShape(),
        )

        did_format = self.check_out(self.node) or self.check_in(self.node)

        if did_format:
            if not self._state_saved and pre_state not in (
                self.out_state,
                self.in_state,
            ):
                self.state = pre_state
                self._state_saved = True
        else:
            if self._state_saved:
                self.node.setColor(self.state[0])
                self.node.setUserData("nodeshape", self.state[1])
                self.state = (default_node_color(self.node), self.type.defaultShape())
            self._state_saved = False

    @staticmethod
    def capitalize(string: str):
        chars = list(string)
        for count, char in enumerate(chars):
            if (count == 0 or string[count - 1] in ("_", "-")) and char.isalpha():
                chars[count] = char.upper()
        return "".join(chars)

    @classmethod
    def check_out(cls, node: hou.OpNode):
        if len(check_name := node.name()) < 3:
            return False
        if not check_name.lower().startswith("out"):
            return False
        if len(check_name) >= 4 and not (check_name[3] in ("-", "_")):
            return False

        node.setName("OUT" + cls.capitalize(check_name[3:]), unique_name=True)
        node.setColor(cls.out_state[0])
        node.setUserData("nodeshape", cls.out_state[1])
        return True

    @classmethod
    def check_in(cls, node: hou.OpNode):
        if len(check_name := node.name()) < 2:
            return False
        if not check_name.lower().startswith("in"):
            return False
        if len(check_name) >= 3 and not (check_name[2] in ("-", "_")):
            return False

        node.setName("IN" + cls.capitalize(check_name[2:]), unique_name=True)
        node.setColor(cls.in_state[0])
        node.setUserData("nodeshape", cls.in_state[1])
        return True
