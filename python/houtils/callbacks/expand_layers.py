import hdefereval
import hou

try:
    from PySide6.QtCore import QModelIndex
except ImportError:
    from PySide2.QtCore import QModelIndex

from scenegraphlayers import panel as base

panel = None
tree = None
model = None
store = {}


def store_state(parent=QModelIndex()):
    global model
    global tree

    if not model or not tree:
        return

    for row in range(model.rowCount(parent)):
        index = model.index(row, 0, parent)
        if index.isValid():
            store[index.data(0)] = tree.isExpanded(index)
            if model.hasChildren(index):
                store_state(index)


def expand(parent=QModelIndex()):
    global model
    global tree

    if not model or not tree:
        return

    for row in range(model.rowCount(parent)):
        index = model.index(row, 0, parent)
        if index.isValid():
            data = index.data(0)
            should_expand = store.get(data, True)
            if should_expand:
                tree.expand(index)
            else:
                tree.collapse(index)
            if model.hasChildren(index):
                expand(index)


def onCreateInterface():
    global panel
    global tree
    global model

    panel = base.SceneGraphLayersPanel()
    tree = panel.view
    model = tree.model()
    return panel


def onActivateInterface():
    global panel

    panel._paneActivated(  # pyright: ignore[reportOptionalMemberAccess]
        kwargs["paneTab"]  # pyright: ignore[reportUndefinedVariable]
    )


def onDeactivateInterface():
    global panel

    panel._paneDeactivated()  # pyright: ignore[reportOptionalMemberAccess]


def onDestroyInterface():
    global panel
    global tree
    global model
    global store

    panel._paneClosed()  # pyright: ignore[reportOptionalMemberAccess]

    panel = None
    tree = None
    model = None
    store = {}


def onNodePathChanged(node):
    global panel
    global tree
    global model
    global store

    store_state()

    panel._panePathChanged(node)  # pyright: ignore[reportOptionalMemberAccess]

    hdefereval.executeDeferred(expand)


def main():
    interface = hou.pypanel.interfaceByName("SceneGraphLayersPanel")
    if not interface:
        return
    interface.setFilePath(__file__)
    with open(__file__, "r") as pwd:
        interface.setScript(pwd.read())
