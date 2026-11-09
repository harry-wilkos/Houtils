import functools
import json
import random
import re

import hdefereval
import hou
from houtils.utils.node import random_color

bookmarks = set()
digit_pattern = re.compile(r"(\d*)$")


class Option:
    def __init__(
        self,
        name: str,
        value: int | None = None,
        type: str | None = None,
        order: int | None = None,
    ):
        self._name = name
        self._value = value
        self._type = type
        self._order = order
        self._config_cache = None

    def config(self) -> dict:
        if self._config_cache is not None:
            return self._config_cache

        config_str = hou.contextOptionConfig(self._name)
        if not config_str:
            self._config_cache = {}
        else:
            try:
                self._config_cache = json.loads(config_str)
            except json.JSONDecodeError:
                self._config_cache = {}

        return self._config_cache

    def name(self) -> str:
        return self._name

    def value(self):
        if self._value is not None:
            return self._value
        return hou.contextOption(self._name)

    def slider_type(self) -> str:
        if self._type is not None:
            return self._type
        return self.config().get("type", "text")

    def save_config(self):
        if self._value is not None:
            if self._type in ("int_slider", "int_menu"):
                val = float(self._value)
            else:
                val = str(self._value)
            if hou.contextOption(self._name) != val:
                hou.setContextOption(self._name, val)

        config = self.config()
        config["type"] = self._type if self._type else "text"

        if self._order is not None:
            config["order"] = self._order

        hou.setContextOptionConfig(self._name, json.dumps(config))

    def save_value(self, value):
        slider_type = self.slider_type()
        val = float(value) if slider_type in ("int_slider", "int_menu") else str(value)

        if hou.contextOption(self._name) != val:
            self._value = value
            hou.setContextOption(self._name, val)
        else:
            self._value = value

    def set_name(self, new_name: str) -> None:
        old_name = self._name
        if old_name == new_name:
            return

        config_str = hou.contextOptionConfig(old_name)
        current_val = self.value()
        current_type = self.slider_type()

        self._name = new_name
        self._config_cache = None

        if current_val is not None:
            val = (
                float(current_val)
                if current_type in ("int_slider", "int_menu")
                else str(current_val)
            )
            if hou.contextOption(new_name) != val:
                hou.setContextOption(new_name, val)

        if config_str:
            hou.setContextOptionConfig(new_name, config_str)

        if hou.hasContextOption(old_name):
            hou.removeContextOption(old_name)

    def set_order(self, order: int) -> None:
        self._order = order
        config = self.config()
        config["order"] = self._order
        hou.setContextOptionConfig(self._name, json.dumps(config))

    def set_range(self, frame_range: tuple) -> None:
        config = self.config()
        f_min, f_max = frame_range

        if config.get("minimum") != f_min or config.get("maximum") != f_max:
            config["minimum"] = f_min
            config["maximum"] = f_max
            hou.setContextOptionConfig(self._name, json.dumps(config))


class SyncManager:
    def __init__(self):
        self.syncing = False
        self.pending_contexts = set()
        self.pending_bookmarks = {}
        self.deferred_queued = False
        self.range_sync = False

    def queue_context(self, context_name):
        if self.syncing:
            return

        if context_name in ("fstart", "fend"):
            self.range_sync = True
            self.schedule_process()
            return

        self.pending_contexts.add(context_name)
        self.schedule_process()

    def queue_bookmark(self, event_type, bookmark_id):
        if self.syncing:
            return
        self.pending_bookmarks[bookmark_id] = event_type
        self.schedule_process()

    def schedule_process(self):
        if not self.deferred_queued:
            self.deferred_queued = True
            hdefereval.executeDeferred(self.process_queues)

    def process_queues(self):
        self.syncing = True
        try:
            if self.range_sync:
                sync_ranges()
                self.range_sync = False

            deleted_keys = set()
            new_keys = set()
            bookmark_names = {
                b.name()
                for b in hou.anim.bookmarks()  # pyright: ignore[reportCallIssue]
            }

            for ctx in self.pending_contexts:
                if hou.isAutoContextOption(ctx):
                    continue

                key, fix, _ = context_to_key(ctx)
                if not fix:
                    if not hou.hasContextOption(ctx):
                        deleted_keys.add(key)
                    elif key not in bookmark_names:
                        new_keys.add(key)

            if len(deleted_keys) == 1 and len(new_keys) == 1:
                old_key = deleted_keys.pop()
                new_key = new_keys.pop()

                for (
                    bookmark
                ) in hou.anim.bookmarks():  # pyright: ignore[reportCallIssue]
                    if bookmark.name() == old_key:
                        bookmark.setMetadata(
                            "houtils:name",
                            new_key,
                            hou.fieldType.String,  # pyright: ignore[reportAttributeAccessIssue]
                        )
                        bookmark.setName(new_key)

                        if old_key in bookmarks:
                            bookmarks.remove(old_key)
                        bookmarks.add(new_key)
                        break

            for ctx in list(self.pending_contexts):
                context_edited(ctx)
            self.pending_contexts.clear()

            for bookmark_id, event_type in list(self.pending_bookmarks.items()):
                bookmark_entry(event_type, bookmark_id)
            self.pending_bookmarks.clear()

        finally:
            self.syncing = False
            self.deferred_queued = False


sync_manager = SyncManager()


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
        if opt_str and '"order"' in opt_str:
            try:
                opt_conf = json.loads(opt_str)
                opt_order = opt_conf.get("order")
                if isinstance(opt_order, int):
                    max_order = max(max_order, opt_order)
            except json.JSONDecodeError:
                pass
    return max_order


def format_name(bookmark) -> str:
    current_name = bookmark.name()
    desired_name = current_name.replace(" ", "_")

    all_names = {
        b.name() for b in hou.anim.bookmarks()  # pyright: ignore[reportCallIssue]
    }
    if current_name in all_names:
        all_names.remove(current_name)

    latest_name = desired_name
    while latest_name in all_names:
        latest_name = digit_pattern.sub(
            lambda m: str(int(m.group(1)) + 1) if m.group(1) else "1",
            latest_name,
            count=1,
        )
    return latest_name


def sync_ranges():
    frame_range = hou.playbar.frameRange()  # pyright: ignore[reportCallIssue]

    active_bookmarks_dict = {
        b.name(): b for b in hou.anim.bookmarks()  # pyright: ignore[reportCallIssue]
    }

    bookmarks_to_delete = set()
    for context_name in hou.contextOptionNames():
        if hou.isAutoContextOption(context_name):
            continue

        key_name, fix, _ = context_to_key(context_name)

        if not fix:
            config_str = hou.contextOptionConfig(context_name)
            if not config_str or (
                '"int_slider"' not in config_str and '"int_menu"' not in config_str
            ):
                continue

            opt = Option(context_name)
            if (val := opt.value()) is None:
                continue

            has_bookmark = key_name in active_bookmarks_dict

            if frame_range[0] <= val <= frame_range[1]:
                opt.set_range(frame_range)
                if not has_bookmark:
                    bookmark = hou.anim.newBookmark(
                        key_name, int(val), int(val)
                    )  # pyright: ignore[reportCallIssue]
                    bookmark.setColor(random_color())
                    bookmark.setMetadata(
                        "houtils:name",
                        key_name,
                        hou.fieldType.String,  # pyright: ignore[reportAttributeAccessIssue]
                    )
                    bookmarks.add(key_name)
                    active_bookmarks_dict[key_name] = bookmark
            else:
                if has_bookmark:
                    bookmarks_to_delete.add(key_name)

        else:
            if key_name in active_bookmarks_dict:
                Option(context_name).set_range(frame_range)

    if bookmarks_to_delete:
        to_delete = [active_bookmarks_dict[name] for name in bookmarks_to_delete]
        if to_delete:
            hou.anim.removeBookmarks(to_delete)  # pyright: ignore[reportCallIssue]


def clean_bookmarks():
    deleted_bookmarks = bookmarks - {
        b.name() for b in hou.anim.bookmarks()  # pyright: ignore[reportCallIssue]
    }
    if not deleted_bookmarks:
        return

    bookmarks.difference_update(deleted_bookmarks)

    for context_name in hou.contextOptionNames():
        if (
            not hou.isAutoContextOption(context_name)
            and (context_to_key(context_name)[0] in deleted_bookmarks)
            and hou.hasContextOption(context_name)
        ):
            hou.removeContextOption(context_name)


def context_edited(context_name: str):
    if hou.isAutoContextOption(context_name):
        return

    bookmark_name, fix, position = context_to_key(context_name)
    opt = Option(context_name)

    if (
        (slider_type := opt.slider_type()) not in ("int_slider", "int_menu")
        and slider_type == "text"
        and hou.contextOption(context_name) is None
        and (
            to_delete := [
                b
                for b in hou.anim.bookmarks()  # pyright: ignore[reportCallIssue]
                if b.name() == bookmark_name
            ]
        )
    ):
        hou.anim.removeBookmarks(to_delete)  # pyright: ignore[reportCallIssue]
        return

    if fix:
        start_name, end_name = get_paired_names(bookmark_name, position)

        if (start_val := hou.contextOption(start_name)) is not None and (
            end_val := hou.contextOption(end_name)
        ) is not None:
            frame_range = hou.playbar.frameRange()  # pyright: ignore[reportCallIssue]
            Option(start_name).set_range(frame_range)
            Option(end_name).set_range(frame_range)

            start_frame, end_frame = int(start_val), int(end_val)

            for bookmark in hou.anim.bookmarks():  # pyright: ignore[reportCallIssue]
                if bookmark.name() != bookmark_name:
                    continue
                if bookmark.startFrame() != start_frame:
                    bookmark.setStartFrame(start_frame)
                if bookmark.endFrame() != end_frame:
                    bookmark.setEndFrame(end_frame)
                return

            new_bookmark = hou.anim.newBookmark(
                bookmark_name, start_frame, end_frame
            )  # pyright: ignore[reportCallIssue]
            new_bookmark.setColor(random_color())
            new_bookmark.setMetadata(
                "houtils:name",
                bookmark_name,
                hou.fieldType.String,  # pyright: ignore[reportAttributeAccessIssue]
            )
            bookmarks.add(bookmark_name)
    else:
        if (val := hou.contextOption(context_name)) is None:
            return
        val = int(val)

        f_min, f_max = hou.playbar.frameRange()  # pyright: ignore[reportCallIssue]
        if f_min <= val <= f_max:
            opt.set_range((f_min, f_max))
            found = False

            for bookmark in hou.anim.bookmarks():  # pyright: ignore[reportCallIssue]
                if bookmark.name() == bookmark_name:
                    if bookmark.startFrame() != val:
                        bookmark.setStartFrame(val)
                    if bookmark.endFrame() != val:
                        bookmark.setEndFrame(val)
                    found = True
                    break

            if not found:
                bookmark = hou.anim.newBookmark(
                    bookmark_name, val, val
                )  # pyright: ignore[reportCallIssue]
                bookmark.setColor(random_color())
                bookmark.setMetadata(
                    "houtils:name",
                    bookmark_name,
                    hou.fieldType.String,  # pyright: ignore[reportAttributeAccessIssue]
                )
                bookmarks.add(bookmark_name)
        elif to_delete := [
            b
            for b in hou.anim.bookmarks()  # pyright: ignore[reportCallIssue]
            if b.name() == bookmark_name
        ]:
            hou.anim.removeBookmarks(to_delete)  # pyright: ignore[reportCallIssue]


def bookmark_entry(event_type, bookmark_id):
    if event_type in (
        hou.bookmarkEvent.Deleted,  # pyright: ignore[reportAttributeAccessIssue]
        hou.bookmarkEvent.Reset,  # pyright: ignore[reportAttributeAccessIssue]
    ):
        clean_bookmarks()
        return

    if (
        bookmark := hou.anim.bookmark(bookmark_id)  # pyright: ignore[reportCallIssue]
    ) and event_type == hou.bookmarkEvent.Modified:  # pyright: ignore[reportAttributeAccessIssue]
        bookmark_edited(bookmark)


def bookmark_edited(bookmark):
    bookmark_name = bookmark.name()

    clone = False
    if stored_name := bookmark.metadata("houtils:name"):
        claimants = [
            b
            for b in hou.anim.bookmarks()  # pyright: ignore[reportCallIssue]
            if b.metadata("houtils:name") == stored_name
        ]
        if len(claimants) > 1:
            if bookmark_name != stored_name:
                clone = True

    name = stored_name if (stored_name and not clone) else None
    if name and (bookmark_name == name):
        latest_name = name
    else:
        latest_name = format_name(bookmark)

    single_opt = None
    start_opt = None
    end_opt = None
    position = 1
    search_name = name if name else latest_name
    if hou.hasContextOption(search_name):
        single_opt = Option(search_name)

    elif hou.hasContextOption(f"start_{search_name}") or hou.hasContextOption(
        f"end_{search_name}"
    ):
        position = 0
        if hou.hasContextOption(f"start_{search_name}"):
            start_opt = Option(f"start_{search_name}")
        if hou.hasContextOption(f"end_{search_name}"):
            end_opt = Option(f"end_{search_name}")

    elif hou.hasContextOption(f"{search_name}_start") or hou.hasContextOption(
        f"{search_name}_end"
    ):
        position = 1
        if hou.hasContextOption(f"{search_name}_start"):
            start_opt = Option(f"{search_name}_start")
        if hou.hasContextOption(f"{search_name}_end"):
            end_opt = Option(f"{search_name}_end")

    start_name, end_name = get_paired_names(latest_name, position)
    start_frame, end_frame = int(bookmark.startFrame()), int(bookmark.endFrame())

    is_single_frame = start_frame == end_frame
    if is_single_frame:
        needs_order = True if not single_opt else False
    else:
        needs_order = True if (not start_opt or not end_opt) else False
    max_order = get_max_order() if needs_order else -1

    if is_single_frame:
        if start_opt and hou.hasContextOption(start_opt.name()):
            hou.removeContextOption(start_opt.name())

        if end_opt and hou.hasContextOption(end_opt.name()):
            hou.removeContextOption(end_opt.name())

        if not single_opt:
            max_order += 1
            single_opt = Option(
                latest_name, value=start_frame, type="int_slider", order=max_order
            )
            single_opt.save_config()
        else:
            single_opt.set_name(latest_name)
            single_opt.save_value(start_frame)

        frame_range = hou.playbar.frameRange()  # pyright: ignore[reportCallIssue]
        single_opt.set_range(frame_range)

    else:
        if single_opt and hou.hasContextOption(single_opt.name()):
            hou.removeContextOption(single_opt.name())

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

        frame_range = hou.playbar.frameRange()  # pyright: ignore[reportCallIssue]
        start_opt.set_range(frame_range)
        end_opt.set_range(frame_range)

    if search_name != latest_name and search_name in bookmarks:
        bookmarks.remove(search_name)

    bookmarks.add(latest_name)

    if bookmark.metadata("houtils:name") != latest_name:
        bookmark.setMetadata(
            "houtils:name",
            latest_name,
            hou.fieldType.String,  # pyright: ignore[reportAttributeAccessIssue]
        )

    if bookmark.name() != latest_name:
        bookmark.setName(latest_name)


def context_entry_callback(context_name: str):
    sync_manager.queue_context(context_name)


def bookmark_entry_callback(event_type, bookmark_id):
    if sync_manager.syncing:
        return

    if (
        event_type
        == hou.bookmarkEvent.Created  # pyright: ignore[reportAttributeAccessIssue]
    ) and (
        bookmark := hou.anim.bookmark(bookmark_id)  # pyright: ignore[reportCallIssue]
    ):
        name = format_name(bookmark)
        bookmarks.add(name)
        if bookmark.metadata("houtils:name") != name:
            bookmark.setMetadata(
                "houtils:name",
                name,
                hou.fieldType.String,  # pyright: ignore[reportAttributeAccessIssue]
            )
        if bookmark.name() != name:
            bookmark.setName(name)

    sync_manager.queue_bookmark(event_type, bookmark_id)


def main():
    hou.anim.addBookmarksChangedCallback(
        bookmark_entry_callback
    )  # pyright: ignore[reportCallIssue]
    hou.addContextOptionChangeCallback(context_entry_callback)
