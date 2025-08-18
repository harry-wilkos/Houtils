import hou

parms = ("resimulate", "reload", "clear", "dirtybutton")

def main():
    store_upate_mode = hou.updateModeSetting()
    hou.setUpdateMode(hou.updateMode.Manual) 
    
    for node in hou.sortedNodes(hou.selectedNodes()):

        # Check if in sim
        parent = node.parent()
        while parent is not None:
            if parent.type().name() == "dopnet":
                parent.parm("resimulate").pressButton()
                break
            parent = parent.parent()
        
        # Reset nodes
        for parm_name in parms:
            if (parm := node.parm(parm_name)):
                parm.pressButton()

        # Cook Nodes
        try:
            node.cook(force=True)
        except hou.OperationFailed:
            pass            

    hou.setUpdateMode(store_upate_mode) 
