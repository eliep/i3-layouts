import logging
from typing import List, Optional

from i3l.layouts import Layouts

from i3l.mover import Mover
from i3l.splitter import Mark
from i3l.state import Context, RebuildCause, State

logger = logging.getLogger(__name__)


class Tick:

    def __init__(self, layouts: Layouts, state: State, action_name: str):
        self._layouts = layouts
        self._state = state
        self._action_name = action_name

    def do(self, context: Context, action_params: List[str]):
        pass

    @staticmethod
    def create(layouts: Layouts, state: State, action_name: str) -> Optional['Tick']:
        if action_name == 'rebuild':
            return None
        elif action_name == 'move':
            return MoveTick(layouts, state, action_name)
        elif action_name == 'swap':
            return SwapTick(layouts, state, action_name)
        elif action_name == 'mark':
            return MarkTick(layouts, state, action_name)
        else:
            return LayoutTick(layouts, state, action_name)


class MoveTick(Tick):

    def do(self, context: Context, action_params: List[str]):
        mover = Mover(context)
        layout = self._layouts.get(context.workspace.name)
        if layout is not None and not layout.is_i3():
            logger.debug('  [ipc] tick event - move container')
            mover.move_to_direction(action_params[0], layout.swap_mark_last())
        else:
            logger.debug('  [ipc] tick event - move command forwarded to i3')
            mover.forward(action_params[0])


class SwapTick(Tick):

    def do(self, context: Context, action_params: List[str]):
        mover = Mover(context)
        if len(action_params) < 3:
            logger.debug('  [ipc] tick event - swap command - not enough parameter')
        workspace_name = context.workspace.name
        destination_mark = Mark.previous() if action_params[-1] == 'previous' else action_params[-1]
        swap_marks = [] if action_params[0] == "container" else [destination_mark]
        logger.debug(f'  [ipc] tick event - swap command to {destination_mark}')
        destination = next(iter(context.tree.find_marked(destination_mark)), None)
        layout = self._layouts.get(workspace_name)
        if destination is not None:
            mover.swap(destination, layout.swap_mark_last() if layout is not None else False, swap_marks)


class MarkTick(Tick):

    def do(self, context: Context, action_params: List[str]):
        context.exec(f'[con_id={context.focused.id}] mark --add {action_params[0]}')


class LayoutTick(Tick):

    def do(self, context: Context, action_params: List[str]):
        layout = Layouts.create(self._action_name, action_params, context.workspace.name)
        if layout is not None:
            logger.debug(f'  [ipc] tick event - set workspace layout to {self._action_name}')
            self._layouts.add(layout)
            self._state.add_workspace_sequence(context.workspace.name)
            self._state.start_rebuild(RebuildCause.layout_change(self._action_name), context, layout.mark_main(),
                                      layout.mark_last())
        else:
            logger.debug('  [ipc] tick event - unset workspace layout')
            self._layouts.remove(context.workspace.name)
