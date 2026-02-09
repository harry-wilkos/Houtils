import re
import hou


def main():
    color = hou.ui.selectColor() 
    if color:
        hou.setSessionModuleSource(
            re.sub(
                r"(houtils_manual_color\s*=\s*)\w.+",
                rf"\g<1>hou.Color({color.rgb()})",
                hou.sessionModuleSource(),
            )
        )

