from houtils.callbacks import In_Out_Format, Auto_Format
import hou

if hou.isUIAvailable():
    In_Out_Format(kwargs)
    Auto_Format(kwargs)
