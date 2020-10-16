from i3ipc import Connection, TickEvent
from i3ipc.events import WorkspaceEvent, WindowEvent
import shlex
import subprocess

from i3l.state import State
from i3l.layouts import Layouts, Layout


def xdo_unmap_window(window_id):
    command = shlex.split(f'xdotool windowunmap {window_id}')
    subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def xdo_map_window(window_id):
    command = shlex.split(f'xdotool windowmap {window_id}')
    subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def containers_after(con_id, containers, state):
    return [con.window for con in containers
            if con_id == 0 or state.window_numbers[con.id] >= state.window_numbers[con_id]]


def redraw_workspace(state: State, layout: Layout, con_id: int = 0):
    containers = state.context.sorted_containers()
    if len(containers) > 0:
        state.containers_to_redraw = containers_after(con_id, containers, state.context.workspace_sequence)
        state.containers_closed = []
        if len(state.containers_to_redraw) > 0:
            for container_window_id in state.containers_to_redraw:
                xdo_unmap_window(container_window_id)
                state.containers_closed.append(container_window_id)
            container_window_id = state.containers_to_redraw.pop(0)
            xdo_map_window(container_window_id)
        else:
            state.context.exec(f'[con_id="{containers[-1].id}"] mark {layout.mark_last()}')


def on_tick(layouts: Layouts, state: State):

    def _on_tick(i3l: Connection, e: TickEvent):
        print('on_tick', e.ipc_data)
        if not e.payload.startswith('i3-layouts'):
            return
        context = state.sync_context(i3l)
        tokens = e.payload.split(' ')
        layout_name = tokens[1]
        layout_params = tokens[2:]
        if layout_name != 'none':
            layout = layouts.add(Layout.create(layout_name, layout_params, context.workspace.name))
            state.add_workspace_sequence(context.workspace.name)
            redraw_workspace(state, layout)
        else:
            layouts.remove(context.workspace.name)
    return _on_tick


def on_workspace_focus(layouts: Layouts, state: State):

    def _on_workspace_focus(i3l: Connection, e: WorkspaceEvent):
        print('on_workspace_focus', e.current.name, e.old.name if e.old else -1, e.ipc_data)
        context = state.sync_context(i3l)
        if layouts.exists_for(e.current.name):
            sequence = state.add_workspace_sequence(e.current.name)
            if state.prev_workspace_name != e.current.name and sequence.is_stale:
                layout = layouts.get(context.workspace.name)
                redraw_workspace(state, layout, sequence.stale_con_id)
                sequence.set_stale(False)
        state.prev_workspace_name = e.current.name
        if e.old:
            state.old_workspace_name = e.old.name
            if layouts.exists_for(e.old.name):
                state.add_workspace_sequence(e.old.name)

    return _on_workspace_focus


def on_window_close(layouts: Layouts, state: State):

    def _on_window_close(i3l: Connection, e: WindowEvent):
        print('on_window_close', e.ipc_data)
        context = state.sync_context(i3l)
        if not layouts.exists_for(context.workspace.name):
            return
        if e.container.window in state.containers_closed:
            state.containers_closed.remove(e.container.window)
            return
        layout = layouts.get(context.workspace.name)
        redraw_workspace(state, layout, e.container.id)

    return _on_window_close


def on_window_move(layouts: Layouts, state: State):

    def _on_window_move(i3l: Connection, e: WindowEvent):
        print('on_window_move', e.ipc_data)
        context = state.sync_context(i3l)
        if context.contains_container(e.container.id) or e.container.type != 'con':
            return
        if layouts.exists_for(state.old_workspace_name):
            sequence = state.get_workspace_sequence(state.old_workspace_name)
            sequence.assign_number(e.container)
            sequence.set_stale(True, e.container.id)
        if layouts.exists_for(context.workspace.name):
            layout = layouts.get(context.workspace.name)
            redraw_workspace(state, layout, e.container.id)

    return _on_window_move


def on_window_new(layouts: Layouts, state: State):

    def _on_window_new(i3l: Connection, e: WindowEvent):
        context = state.sync_context(i3l)
        print('on_window_new', context.workspace.name, e.ipc_data)
        if not layouts.exists_for(context.workspace.name):
            return
        if context.workspace_sequence is None:
            return
        context.workspace_sequence.assign_number(e.container)

        layout = layouts.get(context.workspace.name)
        layout.update(context, e.container)

        if len(state.containers_to_redraw) > 0:
            container_window_id = state.containers_to_redraw.pop(0)
            xdo_map_window(container_window_id)

    return _on_window_new
