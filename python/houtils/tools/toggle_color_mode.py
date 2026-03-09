import hou
from houtils.utils.ui import background_notify
from .set_manual_color import main as set_manual_color

session = hou.session

def main():
    with hou.undos.disabler():
        color_status = not session.houtils_auto_color
        if color_status:
            background_notify(hou.findFile("config/Icons/automatic_color.png"))
        else:
            background_notify(hou.findFile("config/Icons/manual_color.png"))
            if not session.houtils_manual_color:
                set_manual_color()
        session.houtils_auto_color = color_status
