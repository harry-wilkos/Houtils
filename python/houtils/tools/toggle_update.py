import hou
from houtils.utils.ui import background_notify


def main():
    with hou.undos.disabler():
        update_mode = hou.updateModeSetting()
        if update_mode == hou.updateMode.Manual:
            hou.setUpdateMode(hou.updateMode.AutoUpdate)
            background_notify(
                hou.findFile("config/Icons/automatic_update.png"),
            )
        else:
            hou.setUpdateMode(hou.updateMode.Manual)
            background_notify(
                hou.findFile("config/Icons/manual_update.png"),
            )
