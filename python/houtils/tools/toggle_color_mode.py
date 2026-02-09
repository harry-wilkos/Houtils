import hou
from houtils.utils.ui import background_notify

session = hou.session

def main():
    with hou.undos.disabler():
        color_status = not session.houtils_auto_color
        if color_status:
            background_notify(hou.findFile("config/Icons/automatic_color.png"))
        else:
            background_notify(hou.findFile("config/Icons/manual_color.png"))
            if not session.houtils_manual_color:
                color = None
                while not color:
                    color = hou.ui.selectColor() 
                session.houtils_manual_color = color
        session.houtils_auto_color = color_status
