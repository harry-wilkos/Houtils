import re

import hou

session = hou.session
manual_color = f"hou.Color{color.rgb()}" if ( (hasattr(session, "houtils_manual_color")) and (color := session.houtils_manual_color)) else None
auto_color = session.houtils_auto_color if hasattr(session, "houtils_auto_color") else False
source = re.sub(
    r"(houtils_manual_color\s*=\s*)\w.+",
    rf"\g<1>{manual_color}",
    hou.sessionModuleSource(),
)

hou.setSessionModuleSource(
    re.sub(
        r"(houtils_auto_color\s*=\s*)\w.+",
        rf"\g<1>{auto_color}",
        source,
    )
)
