import hou


class In_Out_Format:
    out_state = (hou.Color(1, 1, 1), "bulge")
    in_state = (hou.Color(1, 1, 1), "bulge_down")

    def __init__(self, kwargs: dict):
        node = kwargs["node"]
        node.addEventCallback((hou.nodeEventType.NameChanged,), self.format)

        store_state = (
            node.color(),
            node.userData("nodeshape") or node.type().defaultShape(),
        )
        self.formatted = self.check_out(node) or self.check_in(node)
        self.store_run = self.formatted

        if store_state != self.out_state and store_state != self.in_state:
            self.state = store_state
        else:
            self.state = (
                (node_type := node.type()).defaultColor(),
                node_type.defaultShape(),
            )

    def format(
        self,
        event_type: hou.nodeEventType,  # pyright: ignore[reportUnusedParameter]
        **kwargs: hou.OpNode,
    ):
        node = kwargs["node"]
        store_state = (
            node.color(),
            node.userData("nodeshape") or node.type().defaultShape(),
        )
        self.formatted = self.check_out(node) or self.check_in(node)
        if self.formatted:
            self.store_run = True
            if not (store_state == self.out_state or store_state == self.in_state):
                self.state = store_state
        else:
            if self.store_run:
                node.setColor(self.state[0])
                node.setUserData("nodeshape", self.state[1])
                self.state = (
                    (node_type := node.type()).defaultColor(),
                    node_type.defaultShape(),
                )
            self.store_run = False

    @classmethod
    def check_out(cls, node: hou.OpNode):
        if len(check_name := node.name()) < 3:
            return False
        elif not check_name.lower().startswith("out"):
            return False
        elif len(check_name) >= 4 and not (
            (check_dash := check_name[3]) == "-" or check_dash == "_"
        ):
            return False

        node.setName("OUT" + check_name[3:], unique_name=True)
        node.setColor(cls.out_state[0])
        node.setUserData("nodeshape", cls.out_state[1])
        return True

    @classmethod
    def check_in(cls, node: hou.OpNode):
        if len(check_name := node.name()) < 2:
            return False
        elif not check_name.lower().startswith("in"):
            return False
        elif len(check_name) >= 3 and not (
            (check_dash := check_name[2]) == "-" or check_dash == "_"
        ):
            return False

        node.setName("IN" + check_name[2:], unique_name=True)
        node.setColor(cls.in_state[0])
        node.setUserData("nodeshape", cls.in_state[1])
        return True
