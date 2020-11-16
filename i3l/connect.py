import argparse
import logging
import sys

from i3ipc import Connection, Event

from i3l.config import WorkspaceLayout
from i3l.handlers import on_window_new, on_window_close, on_workspace_focus, on_window_move, on_tick
from i3l.state import State
from i3l.layouts import Layouts


def connect():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()
    log_level = logging.DEBUG if args.debug else logging.INFO

    logging.basicConfig(stream=sys.stdout,
                        format='[%(asctime)s] %(levelname)s {%(filename)s:%(lineno)d} - %(message)s',
                        level=log_level)
    i3 = Connection()

    i3_config = i3.get_config()
    workspace_layouts = WorkspaceLayout.load(i3_config)
    layouts = Layouts([layout for layout in
                       (Layouts.create(workspace_layout.layout_name,
                                       workspace_layout.layout_params,
                                       workspace_layout.workspace_name) for workspace_layout in workspace_layouts)
                       if layout is not None])
    state = State(i3)
    i3.on(Event.WORKSPACE_FOCUS, on_workspace_focus(layouts, state))
    i3.on(Event.WINDOW_NEW, on_window_new(layouts, state))
    i3.on(Event.WINDOW_MOVE, on_window_move(layouts, state))
    i3.on(Event.WINDOW_CLOSE, on_window_close(layouts, state))
    i3.on(Event.TICK, on_tick(layouts, state))

    i3.main()


if __name__ == "__main__":
    connect()
