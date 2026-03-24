if hou.isUIAvailable():
    import hou
    from houtils.callbacks import Auto_Color_Manager, In_Out_Format

    kwargs["loading"] = False
    In_Out_Format(kwargs)
    Auto_Color_Manager.attach_callbacks(kwargs)
