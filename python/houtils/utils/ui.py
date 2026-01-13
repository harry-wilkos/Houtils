from pathlib import Path

import hou

try:
    from PySide6.QtCore import QTimer
except ImportError:
    from PySide2.QtCore import QTimer



def background_notify(
    image_path: str | Path,
    time: int = 500,
    size: float = 0.5,
    transparency: float = 0.5,
    pane: hou.NetworkEditor | None = None,
):
    pane = pane or hou.ui.paneTabOfType(
        hou.paneTabType.NetworkEditor
    )  # pyright: ignore[reportAssignmentType]
    if not pane:
        return

    pixel_size = pane.size()[0] * size
    pane_size = pane.sizeFromScreen(hou.Vector2(pixel_size, pixel_size))
    center = pane.visibleBounds().center()

    image = hou.NetworkImage(
        str(image_path),
        hou.BoundingRect(
            center[0] - pane_size[0] / 2.0,
            center[1] - pane_size[1] / 2.0,
            center[0] + pane_size[0] / 2.0,
            center[1] + pane_size[1] / 2.0,
        ),
    )
    image.setBrightness(transparency)

    def run():
        try:
            pane.setBackgroundImages([image])
            QTimer.singleShot(
                time,
                lambda: pane.setBackgroundImages(  # pyright: ignore[reportAttributeAccessIssue]
                    []
                ),
            )
        except Exception:
            pass
        finally:
            hou.ui.removeEventLoopCallback(run)

    hou.ui.addEventLoopCallback(run)
