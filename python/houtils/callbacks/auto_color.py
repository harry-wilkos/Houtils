import hou


class Auto_Format:
    def __init__(self, kwargs: dict):
        self.node = kwargs["node"]
        self.default = self.node.type().defaultColor()

        self._last_auto_color: hou.Color | None = None
        self._manual_override: bool = False

        self.apply_color()

        self.node.addEventCallback(
            (hou.nodeEventType.InputRewired, hou.nodeEventType.AppearanceChanged),
            self.node_event,
        )

    def node_event(self, event_type: hou.nodeEventType, **kwargs):
        if event_type == hou.nodeEventType.AppearanceChanged:
            current = self.node.color()
            if self._last_auto_color is None:
                if current != self.default:
                    self._manual_override = True
                else:
                    self._manual_override = False
            else:
                self._manual_override = current != self._last_auto_color
        elif event_type == hou.nodeEventType.InputRewired:
            self.apply_color()

    def apply_color(self):
        auto_color = self.default
        if target := self.retrieve_parent(self.node):
            parent_color = self.retrieve_color(target)
            if parent_color is not None:
                auto_color = parent_color

        current_color = self.node.color()

        if not self._manual_override:
            self.node.setColor(auto_color)
            self._last_auto_color = auto_color
            self._manual_override = False
        else:
            if current_color == auto_color:
                self.node.setColor(auto_color)
                self._last_auto_color = auto_color
                self._manual_override = False
            else:
                pass

    @staticmethod
    def retrieve_parent(node: hou.OpNode) -> hou.OpNode | None:
        target = None
        for input in node.inputs():
            while input is not None and not target:
                if not (name := input.name()).startswith("OUT") and not name.startswith(
                    "IN"
                ):
                    target = input
                else:
                    if parents := input.inputs():
                        input = parents[0]
                    else:
                        input = None
        return target

    @staticmethod
    def retrieve_color(node: hou.OpNode) -> hou.Color | None:
        color = node.color()
        if node.type().defaultColor() == color:
            return None
        return color
