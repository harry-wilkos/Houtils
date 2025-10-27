from houtils.callbacks import In_Out_Format, Auto_Color
import hou

if hou.isUIAvailable():
    In_Out_Format(kwargs)
    Auto_Color(kwargs)
