import hdefereval
import hou
from PySide2.QtCore import QModelIndex
from scenegraphlayers import panel as base

panel = None
tree = None
model = None
store = {}


def get_indexes(model, parent=QModelIndex()):
    indexes = []
    for row in range(model.rowCount(parent)):
        if (index := model.index(row, 0, parent)).isValid():
            indexes.append(index)
            if model.hasChildren(index):
                indexes.extend(get_indexes(model, index))
    return indexes


def expand():
    global model
    global tree

    for index in get_indexes(model):
        data = index.data(0)
        if data in store and store[data]:
            tree.expand(index)


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

    panel._paneActivated(kwargs["paneTab"])  # pyright: ignore[reportUndefinedVariable]


def onDeactivateInterface():
    global panel

    panel._paneDeactivated()


def onDestroyInterface():
    global panel
    global tree
    global model
    global store

    panel._paneClosed()

    panel = None
    tree = None
    model = None
    store = {}


def onNodePathChanged(node):
    global panel
    global tree
    global model
    global store

    for index in get_indexes(model):
        store[index.data(0)] = tree.isExpanded(index)

    panel._panePathChanged(node)
    hdefereval.executeDeferred(expand)


def main():
    interface = hou.pypanel.interfaceByName("SceneGraphLayersPanel")
    interface.setFilePath(__file__)
    with open(__file__, "r") as pwd:
        interface.setScript(pwd.read())
