import functools
import json
import re

import hou

from houtils.utils.node import random_color

lock = False
bookmarks = set()


class Option:
    def __init__(self, name: str, value=None, type=None, order=None):
        self._name = name
        self._value = value
        self._type = type
        self._order = order

    def name(self) -> str:
        return self._name

    def value(self):
        if self._value is not None:
            return self._value
        return hou.contextOption(self._name)

    def slider_type(self) -> str:
        if self._type is not None:
            return self._type

        config_str = hou.contextOptionConfig(self._name)
        if not config_str:
            return "text"

        try:
            config = json.loads(config_str)
        except json.JSONDecodeError:
            return "text"

        return config.get("type", "text")

    def save_config(self):
        if self._value is not None:
            if self._type in ("int_slider", "int_menu"):
                val = float(self._value)
            else:
                val = str(self._value)
            hou.setContextOption(self._name, val)

        config_str = hou.contextOptionConfig(self._name)
        try:
            config = json.loads(config_str) if config_str else {}
        except json.JSONDecodeError:
            config = {}

        config["type"] = self._type if self._type else "text"

        if self._order is not None:
            config["order"] = self._order

        hou.setContextOptionConfig(self._name, json.dumps(config))

    def save_value(self, value):
        self._value = value
        t = self.slider_type()
        val = float(value) if t in ("int_slider", "int_menu") else str(value)
        hou.setContextOption(self._name, val)

    def set_name(self, new_name: str) -> None:
        old_name = self._name
        if old_name == new_name:
            return

        config_str = hou.contextOptionConfig(old_name)
        current_val = self.value()

        self._name = new_name
        if current_val is not None:
            t = self.slider_type()
            val = (
                float(current_val)
                if t in ("int_slider", "int_menu")
                else str(current_val)
            )
            hou.setContextOption(new_name, val)

        if config_str:
            hou.setContextOptionConfig(new_name, config_str)

        if hou.hasContextOption(old_name):
            hou.removeContextOption(old_name)

    def set_order(self, order: int) -> None:
        self._order = order
        config_str = hou.contextOptionConfig(self._name)
        try:
            config = json.loads(config_str) if config_str else {}
        except json.JSONDecodeError:
            config = {}

        config["order"] = self._order
        hou.setContextOptionConfig(self._name, json.dumps(config))

    def set_range(self, frame_range: tuple) -> None:
        config_str = hou.contextOptionConfig(self._name)
        try:
            config = json.loads(config_str) if config_str else {}
        except json.JSONDecodeError:
            config = {}

        f_min, f_max = frame_range

        if config.get("minimum") != f_min or config.get("maximum") != f_max:
            config["minimum"] = f_min
            config["maximum"] = f_max
            hou.setContextOptionConfig(self._name, json.dumps(config))


def locked_step(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        global lock
        if lock:
            return
        lock = True
        try:
            return func(*args, **kwargs)
        finally:
            lock = False

    return wrapper


def context_to_key(context_name: str) -> tuple[str, str, int]:
    if context_name.endswith("_start"):
        return context_name.removesuffix("_start"), "_start", 1
    if context_name.endswith("_end"):
        return context_name.removesuffix("_end"), "_end", 1
    if context_name.startswith("start_"):
        return context_name.removeprefix("start_"), "start_", 0
    if context_name.startswith("end_"):
        return context_name.removeprefix("end_"), "end_", 0
    return context_name, "", -1


def get_paired_names(bookmark_name: str, position: int) -> tuple[str, str]:
    if position == 1:
        return f"{bookmark_name}_start", f"{bookmark_name}_end"
    return f"start_{bookmark_name}", f"end_{bookmark_name}"


def get_max_order() -> int:
    max_order = -1
    for opt_name in hou.contextOptionNames():
        if hou.isAutoContextOption(opt_name):
            continue
        opt_str = hou.contextOptionConfig(opt_name)
        if opt_str:
            try:
                opt_conf = json.loads(opt_str)
                opt_order = opt_conf.get("order")
                if isinstance(opt_order, int):
                    max_order = max(max_order, opt_order)
            except json.JSONDecodeError:
                pass
    return max_order


def sync_ranges():
    frame_range = hou.playbar.frameRange()
    f_min, f_max = frame_range

    all_bookmarks = hou.anim.bookmarks()
    active_bookmark_names = {b.name() for b in all_bookmarks}

    bookmarks_to_delete = set()
    all_options = hou.contextOptionNames()

    for context_name in all_options:
        if hou.isAutoContextOption(context_name):
            continue

        key_name, fix, _ = context_to_key(context_name)
        opt = Option(context_name)

        if not fix:
            if opt.slider_type() not in ("int_slider", "int_menu"):
                continue

            val = opt.value()
            if val is not None:
                in_range = f_min <= val <= f_max
                has_bookmark = key_name in active_bookmark_names

                if in_range:
                    opt.set_range(frame_range)
                    if not has_bookmark:
                        b = hou.anim.newBookmark(key_name, int(val), int(val))
                        b.setColor(random_color())
                        b.setMetadata(
                            "houtils:name", key_name, hou.fieldType.String
                        )  # Added metadata init
                        bookmarks.add(key_name)
                        active_bookmark_names.add(key_name)
                else:
                    if has_bookmark:
                        bookmarks_to_delete.add(key_name)

        else:
            if key_name in active_bookmark_names:
                opt.set_range(frame_range)

    if bookmarks_to_delete:
        to_delete = [b for b in hou.anim.bookmarks() if b.name() in bookmarks_to_delete]
        if to_delete:
            hou.anim.removeBookmarks(to_delete)


@locked_step
def context_entry(context_name: str):
    if hou.isAutoContextOption(context_name):
        if context_name in ("fstart", "fend"):
            sync_ranges()
        return

    bookmark_name, fix, position = context_to_key(context_name)
    opt = Option(context_name)
    opt_type = opt.slider_type()

    if opt_type not in ("int_slider", "int_menu"):
        if opt_type == "text" and hou.contextOption(context_name) is None:
            to_delete = [b for b in hou.anim.bookmarks() if b.name() == bookmark_name]
            if to_delete:
                hou.anim.removeBookmarks(to_delete)
        return

    if fix:
        start_name, end_name = get_paired_names(bookmark_name, position)
        start_val = hou.contextOption(start_name)
        end_val = hou.contextOption(end_name)

        if start_val is not None and end_val is not None:
            frame_range = hou.playbar.frameRange()
            Option(start_name).set_range(frame_range)
            Option(end_name).set_range(frame_range)

            start_frame, end_frame = int(start_val), int(end_val)

            for b in hou.anim.bookmarks():
                if b.name() == bookmark_name:
                    b.setStartFrame(start_frame)
                    b.setEndFrame(end_frame)
                    return

            b = hou.anim.newBookmark(bookmark_name, start_frame, end_frame)
            b.setColor(random_color())
            b.setMetadata(
                "houtils:name", bookmark_name, hou.fieldType.String
            )  # Added metadata init
            bookmarks.add(bookmark_name)
    else:
        val = hou.contextOption(context_name)
        if val is not None:
            frame_val = int(val)
            f_min, f_max = hou.playbar.frameRange()

            if f_min <= val <= f_max:
                opt.set_range((f_min, f_max))
                found = False

                for b in hou.anim.bookmarks():
                    if b.name() == bookmark_name:
                        b.setStartFrame(frame_val)
                        b.setEndFrame(frame_val)
                        found = True
                        break

                if not found:
                    b = hou.anim.newBookmark(bookmark_name, frame_val, frame_val)
                    b.setColor(random_color())
                    b.setMetadata(
                        "houtils:name", bookmark_name, hou.fieldType.String
                    )  # Added metadata init
                    bookmarks.add(bookmark_name)
            else:
                to_delete = [
                    b for b in hou.anim.bookmarks() if b.name() == bookmark_name
                ]
                if to_delete:
                    hou.anim.removeBookmarks(to_delete)


def format_name(name: str) -> str:
    latest_name = name.replace(" ", "_")
    existing_names = [b.name() for b in hou.anim.bookmarks()]

    if existing_names.count(latest_name) <= 1:
        return latest_name

    existing_set = set(existing_names)
    while latest_name in existing_set:
        latest_name = re.sub(
            r"(\d*)$",
            lambda m: str(int(m.group(1)) + 1) if m.group(1) else "1",
            latest_name,
            count=1,
        )
    return latest_name


def clean_bookmarks():
    current_bookmarks = {b.name() for b in hou.anim.bookmarks()}
    deleted_bookmarks = bookmarks - current_bookmarks

    for name in deleted_bookmarks:
        bookmarks.remove(name)

        options_to_remove = []
        for context_name in hou.contextOptionNames():
            if not hou.isAutoContextOption(context_name):
                key_name, _, _ = context_to_key(context_name)
                if key_name == name:
                    options_to_remove.append(context_name)

        for opt in options_to_remove:
            hou.removeContextOption(opt)


def bookmark_edited(bookmark):
    latest_name = format_name(bookmark.name())
    meta_name = bookmark.metadata("houtils:name")
    name = latest_name if not meta_name else meta_name

    position = 1
    single_opt = None
    start_opt = None
    end_opt = None

    for context_name in hou.contextOptionNames():
        if hou.isAutoContextOption(context_name):
            continue

        key_name, fix, pos = context_to_key(context_name)
        if key_name == name:
            if not fix:
                single_opt = Option(context_name)
            else:
                if pos != -1:
                    position = pos
                if "start" in fix:
                    start_opt = Option(context_name)
                elif "end" in fix:
                    end_opt = Option(context_name)

    start_name, end_name = get_paired_names(latest_name, position)
    start_frame, end_frame = int(bookmark.startFrame()), int(bookmark.endFrame())

    is_single_frame = start_frame == end_frame

    if is_single_frame:
        if start_opt and hou.hasContextOption(start_opt.name()):
            hou.removeContextOption(start_opt.name())
        if end_opt and hou.hasContextOption(end_opt.name()):
            hou.removeContextOption(end_opt.name())

        max_order = get_max_order() if not single_opt else -1

        if not single_opt:
            max_order += 1
            single_opt = Option(
                latest_name, value=start_frame, type="int_slider", order=max_order
            )
            single_opt.save_config()
        else:
            single_opt.set_name(latest_name)
            single_opt.save_value(start_frame)

        frame_range = hou.playbar.frameRange()
        single_opt.set_range(frame_range)

    else:
        if single_opt and hou.hasContextOption(single_opt.name()):
            hou.removeContextOption(single_opt.name())

        max_order = get_max_order() if (not start_opt or not end_opt) else -1

        if not start_opt:
            max_order += 1
            start_opt = Option(
                start_name, value=start_frame, type="int_slider", order=max_order
            )
            start_opt.save_config()
        else:
            start_opt.set_name(start_name)
            start_opt.save_value(start_frame)

        if not end_opt:
            max_order += 1
            end_opt = Option(
                end_name, value=end_frame, type="int_slider", order=max_order
            )
            end_opt.save_config()
        else:
            end_opt.set_name(end_name)
            end_opt.save_value(end_frame)

        frame_range = hou.playbar.frameRange()
        start_opt.set_range(frame_range)
        end_opt.set_range(frame_range)

    if name != latest_name and name in bookmarks:
        bookmarks.remove(name)
    bookmarks.add(latest_name)

    bookmark.setMetadata("houtils:name", latest_name, hou.fieldType.String)
    bookmark.setName(latest_name)


@locked_step
def bookmark_entry(event_type, bookmark_id):
    if event_type in (hou.bookmarkEvent.Deleted, hou.bookmarkEvent.Reset):
        clean_bookmarks()
        return

    bookmark = hou.anim.bookmark(bookmark_id)
    if not bookmark:
        return

    if event_type == hou.bookmarkEvent.Created:
        name = format_name(bookmark.name())
        bookmarks.add(name)
        bookmark.setName(name)
        bookmark.setMetadata(
            "houtils:name", name, hou.fieldType.String
        )  # Added metadata init
    elif event_type == hou.bookmarkEvent.Modified:
        bookmark_edited(bookmark)


def main():
    hou.anim.addBookmarksChangedCallback(bookmark_entry)
    hou.addContextOptionChangeCallback(context_entry)
