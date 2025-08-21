import hou
from houtils.util.ui import background_notify


def main():
    update_mode = hou.updateModeSetting()
    pane = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
    if update_mode == hou.updateMode.Manual:
        hou.setUpdateMode(hou.updateMode.AutoUpdate)
        if pane:
            background_notify(
                hou.findFile("icons/automatic_update.png"),
                pane=pane,  # pyright: ignore[reportArgumentType]
            )
    else:
        hou.setUpdateMode(hou.updateMode.Manual)
        if pane:
            background_notify(
                hou.findFile("icons/manual_update.png"),
                pane=pane,  # pyright: ignore[reportArgumentType]
            )
