import hou
from houtils.utils.ui import default_node_color
from houtils.utils.ui import background_notify

def main():
    with hou.undos.group("All nodes set to their default color"):
        nodes = hou.sortedNodes(hou.selectedNodes())
        if not nodes:
            return

        store_upate_mode = hou.updateModeSetting()
        hou.setUpdateMode(hou.updateMode.Manual)
        for node in nodes:
            node.setColor(default_node_color(node))
        hou.setUpdateMode(store_upate_mode)
        background_notify(hou.findFile("config/Icons/clear_colors.png"))
