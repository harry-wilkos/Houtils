import hou
from hutil.PySide import QtWidgets  # pyright: ignore[reportUnusedImport]
from PySide2 import QtCore
from scenegraphlayers import panel

thePanel = None
theTree = None


def onCreateInterface():
    global thePanel
    global theTree
    thePanel = panel.SceneGraphLayersPanel()
    theTree = thePanel.findChild(panel.SceneGraphLayersTree)
    return thePanel


def onActivateInterface():
    global thePanel
    thePanel._paneActivated(kwargs["paneTab"])


def onDeactivateInterface():
    global thePanel
    thePanel._paneDeactivated()


def onDestroyInterface():
    global thePanel
    global theTree
    thePanel._paneClosed()
    thePanel = None
    theTree = None


def onNodePathChanged(node):
    global thePanel
    global theTree
    thePanel._panePathChanged(node)
    QtCore.QTimer.singleShot(1000, theTree.expandAll)


def main():
    interface = hou.pypanel.interfaceByName("SceneGraphLayersPanel")
    interface.setFilePath(__file__)
    with open(__file__, "r") as pwd:
        interface.setScript(pwd.read())
