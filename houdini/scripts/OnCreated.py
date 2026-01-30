import hou
from houtils.callbacks import Auto_Color, In_Out_Format

if hou.isUIAvailable():
    kwargs["loading"] = False
    In_Out_Format(kwargs)
    Auto_Color(kwargs)
