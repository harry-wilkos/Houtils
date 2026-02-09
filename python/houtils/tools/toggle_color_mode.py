import re

import hou
from houtils.utils.ui import background_notify


def main():
    with hou.undos.disabler():
        color_status = not hou.session.houtils_auto_color
        if color_status:
            background_notify(hou.findFile("config/Icons/automatic_color.png"))
        else:
            background_notify(hou.findFile("config/Icons/manual_color.png"))
            if not hou.session.houtils_manual_color:
                color = None
                while not color:
                    color = hou.ui.selectColor() 
                hou.setSessionModuleSource(
                    re.sub(
                        r"(houtils_manual_color\s*=\s*)\w.+",
                        rf"\g<1>hou.Color({color.rgb()})",
                        hou.sessionModuleSource(),
                    )
                )
        hou.setSessionModuleSource(
            re.sub(
                r"(houtils_auto_color\s*=\s*)\w.+",
                rf"\g<1>{color_status}",
                hou.sessionModuleSource(),
            )
        )
