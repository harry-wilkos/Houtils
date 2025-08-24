import hou


def main(attrib: str, new_dop_objects, existing_dop_objects):
    for dop_object in set(new_dop_objects + existing_dop_objects):
        attrib_geo = dop_object.fieldGeometry(attrib)
        if not attrib_geo:
            continue

        for prim in attrib_geo.prims():
            if type(prim) is hou.Volume and (
                attrib_data := dop_object.findSubData(attrib)
            ):
                attrib_data.options().setField("min", prim.volumeMin())
                attrib_data.options().setField("max", prim.volumeMax())
