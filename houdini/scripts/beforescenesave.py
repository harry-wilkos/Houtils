import re

import hou

session = hou.session
manual_color = color.rgb() if (color := session.houtils_manual_color) else None
source = re.sub(
    r"(houtils_manual_color\s*=\s*)\w.+",
    rf"\g<1>hou.Color({manual_color})",
    hou.sessionModuleSource(),
)

hou.setSessionModuleSource(
    re.sub(
        r"(houtils_auto_color\s*=\s*)\w.+",
        rf"\g<1>{session.houtils_auto_color}",
        source,
    )
)
