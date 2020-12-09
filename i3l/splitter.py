from enum import Enum
from typing import Optional, Any, List

from i3l.options import Direction
from i3l.state import Context


class Markable:

    def get_workspace_name(self):
        pass

    def mark_main(self):
        return f'i3l:{self.get_workspace_name()}:main'

    def mark_last(self):
        return f'i3l:{self.get_workspace_name()}:last'


class Splittable(Markable):

    def split_direction(self, context: Context) -> Optional[Direction]:
        pass

    def stack_direction(self, context: Context) -> Optional[Direction]:
        pass


class Splitter:
    def __init__(self, context: Context):
        self._context = context

    def handle_split(self, splittable: Splittable):
        previous_lasts = self._context.tree.find_marked(splittable.mark_last())
        if len(previous_lasts) == 0:
            return
        previous_last = previous_lasts[0]
        con_id = previous_last.id
        split_direction = self._safe_enum_value(splittable.split_direction(self._context))
        stack_direction = self._safe_enum_value(splittable.stack_direction(self._context))
        if split_direction is not None:
            self._context.exec(f'[con_id="{con_id}"] split {split_direction}')
        elif stack_direction is not None:
            sibling_ids = [sibling.id for sibling in previous_last.parent.descendants()]
            move_direction = 'down' if stack_direction == 'vertical' else 'right'
            if len(sibling_ids) == 1 or self._contains_focused(sibling_ids):
                self._context.exec(f'[con_id="{con_id}"] move {move_direction}')
                if self._contains_focused(sibling_ids) and previous_last.parent.orientation == stack_direction:
                    self._context.exec(f'[con_id="{con_id}"] move {move_direction}')

    def _contains_focused(self, sibling_ids: List[str]):
        return len(sibling_ids) == 2 and self._context.focused.id in sibling_ids

    @staticmethod
    def _safe_enum_value(enum: Enum) -> Optional[Any]:
        return enum.value if enum is not None else None
