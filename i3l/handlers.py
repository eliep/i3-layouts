from typing import List

from i3ipc import Connection, TickEvent
from i3ipc.events import WorkspaceEvent, WindowEvent
import logging

from i3l.state import State, RebuildCause, Context, is_layout_container
from i3l.layouts import Layouts

logger = logging.getLogger(__name__)


def on_tick(layouts: Layouts, state: State):

    def handle_move_tick(context: Context, action_params: List[str]):
        if layouts.exists_for(context.workspace.name) and not layouts.get(context.workspace.name).is_i3():
            logger.debug(f'  [ipc] workspace layouts exists for {context.workspace.name}')
            layout = layouts.get(context.workspace.name)
            layout.move(context, action_params[0])
        else:
            context.exec(f'move {action_params[0]}')

    def handle_layout_tick(context: Context, action_name: str, action_params: List[str]):
        layout = Layouts.create(action_name, action_params, context.workspace.name)
        if layout is not None:
            logger.debug(f'  [ipc] tick event - set workspace layout to {action_name}')
            layouts.add(layout)
            state.add_workspace_sequence(context.workspace.name)
            state.start_rebuild(RebuildCause.layout_change(action_name), context,
                                layout.mark_main(), layout.mark_last())
        else:
            logger.debug('  [ipc] tick event - unset workspace layout')
            layouts.remove(context.workspace.name)

    def _on_tick(i3l: Connection, e: TickEvent):
        logger.debug(f'[ipc] tick event - payload:{e.payload}')
        if not e.payload.startswith('i3-layouts'):
            return
        context = state.sync_context(i3l)
        tokens = e.payload.split(' ')
        action_name = tokens[1]
        action_params = tokens[2:]
        if action_name == 'rebuild':
            pass
        elif action_name == 'move':
            handle_move_tick(context, action_params)
        else:
            handle_layout_tick(context, action_name, action_params)

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
        if state.rebuild_closed_container(e.container.window):
            state.remove_closed_container(e.container.window)
            return
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
        context.workspace_sequence.set_order(e.container)

        logger.debug('  [ipc] window new event - update layout')
        layout = layouts.get(context.workspace.name)
        layout.update(context, e.container)

        if not state.has_rebuild_in_progress():
            state.end_rebuild(context, RebuildCause.WINDOW_NEW)
        elif state.is_rebuild_finished():
            state.end_rebuild(context)
        else:
            state.recreate_next_window(context)

    return _on_window_new
