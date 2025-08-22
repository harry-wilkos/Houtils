import hou


def main():
    for count, node in enumerate(hou.pwd().inputs()):
        if node.geometry():  # pyright: ignore[reportAttributeAccessIssue]
            return count
    return 0
