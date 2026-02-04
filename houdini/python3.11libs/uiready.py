from houtils.callbacks import expand_layers
import hou

if hou.isUIAvailable():
    if not hasattr(hou.session, "houtils_auto_color"):
        hou.appendSessionModuleSource("houtils_auto_color = False")
    expand_layers()
