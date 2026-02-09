import re

import hou

session = hou.session

def main():
    color = hou.ui.selectColor() 
    if color:
        session.houtils_manual_color = color 
