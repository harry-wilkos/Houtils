if hou.isUIAvailable():
    import hou
    from houtils.callbacks import Auto_Color, In_Out_Format

    kwargs["loading"] = False
    In_Out_Format(kwargs)
    Auto_Color.attach_callbacks(kwargs)
