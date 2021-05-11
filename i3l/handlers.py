from i3ipc import Connection, TickEvent
from i3ipc.events import WorkspaceEvent, WindowEvent
import logging

from i3l.options import LayoutName
from i3l.splitter import Mark
from i3l.state import State, RebuildCause, is_layout_container, is_floating_container
from i3l.layouts import Layouts
from i3l.ticks import Tick

logger = logging.getLogger(__name__)


def on_tick(layouts: Layouts, state: State):

    def _on_tick(i3l: Connection, e: TickEvent):
        logger.debug(f'[ipc] tick event - payload:{e.payload}')
        if not e.payload.startswith('i3-layouts'):
            return
        context = state.sync_context(i3l)
        tokens = e.payload.split(' ')
        action_name = tokens[1]
        action_params = tokens[2:]
        tick = Tick.create(layouts, state, action_name)
        if tick is not None:
            tick.do(context, action_params)

    return _on_tick


def on_workspace_focus(layouts: Layouts, state: State):

    def _on_workspace_focus(i3l: Connection, e: WorkspaceEvent):
        logger.debug(f'[ipc] workspace focus event - workspace:{e.current.name}, old:{e.old.name if e.old else "none"}')
        context = state.sync_context(i3l)
        if layouts.exists_for(e.current.name):
            logger.debug(f'  [ipc] workspace layouts exists for {e.current.name}')
            sequence = state.add_workspace_sequence(e.current.name)
            if state.prev_workspace_name != e.current.name and sequence.is_stale:
                layout = layouts.get(context.workspace.name)
                con_id = sequence.stale_con_id
                state.start_rebuild(RebuildCause.WORKSPACE_FOCUS, context,
                                    layout.mark_main(), layout.mark_last(), con_id)
                sequence.set_stale(False)
            elif state.prev_workspace_name != e.current.name:
                state.end_rebuild(context, RebuildCause.WORKSPACE_FOCUS)
        else:
            logger.debug(f'  [ipc] no workspace layouts exists for {e.current.name}')
            state.end_rebuild(context, RebuildCause.WORKSPACE_FOCUS)

        state.prev_workspace_name = e.current.name
        if e.old:
            state.old_workspace_name = e.old.name
            if layouts.exists_for(e.old.name):
                state.add_workspace_sequence(e.old.name)

    return _on_workspace_focus


def on_window_close(layouts: Layouts, state: State):

    def _on_window_close(i3l: Connection, e: WindowEvent):
        logger.debug(f'[ipc] window close event - container:{e.container.id}')
        context = state.sync_context(i3l)
        if not layouts.exists_for(context.workspace.name):
            logger.debug('  [ipc] window close event - no workspace layout')
            return
        if not state.rebuild_closed_container(e.container.window):
            layout = layouts.get(context.workspace.name)
            state.start_rebuild(RebuildCause.WINDOW_CLOSE, context,
                                layout.mark_main(), layout.mark_last(), e.container.id)

    return _on_window_close


def on_window_move(layouts: Layouts, state: State):

    def _on_window_move(i3l: Connection, e: WindowEvent):
        logger.debug(f'[ipc] window move event - container:{e.container.id}')
        context = state.sync_context(i3l)
        if context.contains_container(e.container.id) or e.container.type != 'con':
            logger.debug('  [ipc] window move event - inside workspace')
            return
        if layouts.exists_for(state.old_workspace_name):
            logger.debug('  [ipc] window move event - to another workspace')
            sequence = state.get_workspace_sequence(state.old_workspace_name)
            sequence.set_order(e.container)
            sequence.set_stale(True, e.container.id)
        if layouts.exists_for(context.workspace.name):
            layout = layouts.get(context.workspace.name)
            state.start_rebuild(RebuildCause.WINDOW_MOVE, context,
                                layout.mark_main(), layout.mark_last(), e.container.id)

    return _on_window_move


def on_window_new(layouts: Layouts, state: State):

    def _on_window_new(i3l: Connection, e: WindowEvent):
        logger.debug(f'[ipc] window new event - container:{e.container.id}:{e.container.window}')
        context = state.sync_context(i3l)
        if not layouts.exists_for(context.workspace.name) or context.workspace_sequence is None:
            logger.debug('  [ipc] window new event - no workspace layout')
            return
        if not is_layout_container(e.container):
            logger.debug('  [ipc] window new event - not a layout container')
            return
        if len(context.containers) == 0:
            logger.debug('  [ipc] window new event - no container to handle')
            return
        context.workspace_sequence.set_order(e.container)

        logger.debug('  [ipc] window new event - update layout')
        layout = layouts.get(context.workspace.name)
        layout.update(context, e.container)

        state.handle_rebuild(context, e.container)

    return _on_window_new


def on_window_floating(layouts: Layouts, state: State):

    def _on_window_floating(i3l: Connection, e: WindowEvent):
        logger.debug(f'[ipc] window floating event - container:{e.container.id}:{e.container.window}')
        if is_floating_container(e.container):
            if not state.is_last_container_rebuilt(e.container):
                state.rebuild_action.container_id_to_focus = e.container.id
                on_window_close(layouts, state)(i3l, e)
            else:
                state.rebuild_action.last_container_rebuilt = None
                context = state.sync_context(i3l)
                context.exec(f'[con_id={e.container.id}] floating disable')
        else:
            on_window_new(layouts, state)(i3l, e)

    return _on_window_floating


def on_window_focus(layouts: Layouts, state: State):

    def _on_window_focus(i3l: Connection, e: WindowEvent):
        logger.debug(f'[ipc] window focus event - container:{e.container.id}:{e.container.window}')
        context = state.sync_context(i3l)
        layout = layouts.get(context.workspace.name)
        focused_container = i3l.get_tree().find_focused()
        if not is_layout_container(focused_container):
            logger.debug('  [ipc] window focus event - not a layout container')
            return
        previous_mark = Mark.previous()
        current_mark = Mark.current()
        i3l.command(f'[con_mark="{current_mark}"] mark --add {previous_mark}')
        i3l.command(f'[con_id="{focused_container.id}"] mark --add {current_mark}')
        if layout is None:
            logger.debug('  [ipc] window focus event - no workspace layout')
            return
        if layout.name != LayoutName.AUTOSPLIT:
            logger.debug('  [ipc] window focus event - workspace layout not autosplit')
            return

        logger.debug('  [ipc] window focus event - update layout')
        layout.update(context, focused_container)

    return _on_window_focus
