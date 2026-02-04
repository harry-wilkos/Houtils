from houtils.callbacks import expand_layers
import hou
import re

if hou.isUIAvailable():
    if (match := re.search(r"^untitled.hip*", hou.hipFile.name())):
        hou.appendSessionModuleSource("houtils_auto_color = True")
    elif not hasattr(hou.session, "houtils_auto_color"):
        hou.appendSessionModuleSource("houtils_auto_color = False")

    expand_layers()
