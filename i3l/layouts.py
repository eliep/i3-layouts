import logging
from enum import Enum
from typing import List, Optional, Any, Union

from i3ipc import Con

from i3l.state import Context

logger = logging.getLogger(__name__)


class LayoutName(Enum):
    VSTACK = 'vstack'
    HSTACK = 'hstack'
    SPIRAL = 'spiral'
    THREE_COLUMNS = '3columns'
    COMPANION = 'companion'


class HorizontalPosition(Enum):
    RIGHT = 'right'
    LEFT = 'left'


class VerticalPosition(Enum):
    UP = 'up'
    DOWN = 'down'


class AlternateVerticalPosition(Enum):
    UP = 'up'
    DOWN = 'down'
    ALTUP = 'alt-up'
    ALTDOWN = 'alt-down'


class Direction(Enum):
    VERTICAL = 'vertical'
    HORIZONTAL = 'horizontal'


class ScreenDirection(Enum):
    INSIDE = 'inside'
    OUTSIDE = 'outside'


class ResizeDirection(Enum):
    WIDTH = 'width'
    HEIGHT = 'height'


class Layout:
    def __init__(self, layout_name: LayoutName, workspace_name: str):
        self.name = layout_name
        self.workspace_name = workspace_name

    def _warn_wrong_parameters(self, params: List[Any]):
        logger.warning(f'[layouts] Invalid {self.name.value} layout parameters {params}, '
                       f'using default {self._params()}')

    def _params(self) -> List[Any]:
        pass

    def mark_main(self):
        return f'i3l:{self.workspace_name}:main'

    def mark_last(self):
        return f'i3l:{self.workspace_name}:last'

    def anchor_mark(self) -> str:
        pass

    def update(self, context: Context, con: Con):
        containers = context.containers
        if len(containers) > 1:
            context.exec(f'[con_id="{con.id}"] move window to mark {self.anchor_mark()}')

        mark = self.mark_main() if len(containers) == 1 else self.mark_last()
        context.exec(f'mark {mark}')
        self._update(context)

    def _update(self, context: Context):
        pass

    @staticmethod
    def create(name: str, params: List[Any], workspace_name: str) -> Optional['Layout']:
        try:
            layout_name = LayoutName(name)
        except ValueError:
            logger.error(f'[layouts] Invalid layout name: {name}')
            return None

        if layout_name == LayoutName.VSTACK:
            return VStack(workspace_name, params)
        elif layout_name == LayoutName.HSTACK:
            return HStack(workspace_name, params)
        elif layout_name == LayoutName.SPIRAL:
            return Spiral(workspace_name, params)
        elif layout_name == LayoutName.THREE_COLUMNS:
            return ThreeColumns(workspace_name, params)
        elif layout_name == LayoutName.COMPANION:
            return Companion(workspace_name, params)


class Stack(Layout):
    def __init__(self, layout_name: LayoutName, workspace_name: str, params: List[Any]):
        super().__init__(layout_name, workspace_name)
        try:
            self.main_ratio = float(params[0]) if len(params) > 0 else 0.5
            self.second_axe_position = self._second_axe_position(params[1]) \
                if len(params) > 1 else self._default_second_axe_position()
        except ValueError:
            self.main_ratio = 0.5
            self.second_axe_position = self._default_second_axe_position()
            self._warn_wrong_parameters(params)

    def _params(self) -> List[Any]:
        return [self.main_ratio, self.second_axe_position.value]

    def anchor_mark(self) -> str:
        return self.mark_last()

    def _update(self, context: Context):
        if len(context.containers) == 1:
            context.exec(f'split {self._first_direction().value}')
        elif len(context.containers) == 2:
            context.exec(f'move {self.second_axe_position.value}')
            size = context.workspace_width(1 - self.main_ratio) \
                if self._resize_direction() == ResizeDirection.WIDTH else context.workspace_height(1 - self.main_ratio)
            context.exec(f'resize set {self._resize_direction().value} {size}')
            context.exec(f'split {self._second_direction().value}')

    def _first_direction(self) -> Direction:
        pass

    def _second_direction(self) -> Direction:
        pass

    def _resize_direction(self) -> ResizeDirection:
        pass

    def _second_axe_position(self, second_axe_position: str) -> Union[HorizontalPosition, VerticalPosition]:
        pass

    def _default_second_axe_position(self) -> Union[HorizontalPosition, VerticalPosition]:
        pass


class VStack(Stack):

    def __init__(self, workspace_name: str, params: List[Any]):
        super().__init__(LayoutName.VSTACK, workspace_name, params)

    def _first_direction(self) -> Direction:
        return Direction.HORIZONTAL

    def _second_direction(self) -> Direction:
        return Direction.VERTICAL

    def _resize_direction(self) -> ResizeDirection:
        return ResizeDirection.WIDTH

    def _second_axe_position(self, second_axe_position: str) -> HorizontalPosition:
        return HorizontalPosition(second_axe_position)

    def _default_second_axe_position(self) -> HorizontalPosition:
        return HorizontalPosition.RIGHT


class HStack(Stack):

    def __init__(self, workspace_name: str, params: List[Any]):
        super().__init__(LayoutName.HSTACK, workspace_name, params)

    def _first_direction(self) -> Direction:
        return Direction.VERTICAL

    def _second_direction(self) -> Direction:
        return Direction.HORIZONTAL

    def _resize_direction(self) -> ResizeDirection:
        return ResizeDirection.HEIGHT

    def _second_axe_position(self, second_axe_position: str) -> VerticalPosition:
        return VerticalPosition(second_axe_position)

    def _default_second_axe_position(self) -> VerticalPosition:
        return VerticalPosition.UP


class Spiral(Layout):

    def __init__(self, workspace_name: str, params: List[Any]):
        super().__init__(LayoutName.SPIRAL, workspace_name)
        try:
            self.main_ratio = float(params[0]) if len(params) > 0 else 0.5
            self.screen_direction = ScreenDirection(params[1]) if len(params) > 1 else ScreenDirection.INSIDE
        except ValueError:
            self.main_ratio = 0.5
            self.screen_direction = ScreenDirection.INSIDE
            self._warn_wrong_parameters(params)

    def _params(self) -> List[Any]:
        return [self.main_ratio, self.screen_direction.value]

    def anchor_mark(self) -> str:
        return self.mark_last()

    def _update(self, context: Context):
        if len(context.containers) % 2 == 1:
            if self.screen_direction == ScreenDirection.INSIDE and ((len(context.containers) - 1) / 2) % 2 == 0:
                context.exec('move up')
            context.exec('split horizontal')
            if len(context.containers) > 1:
                ratio = pow(1 - self.main_ratio, (len(context.containers) - 1) / 2)
                context.exec(f'resize set height {context.workspace_height(ratio)}')
        else:
            if self.screen_direction == ScreenDirection.INSIDE and (len(context.containers) / 2) % 2 == 0:
                context.exec('move left')
            context.exec('split vertical')
            ratio = pow(1 - self.main_ratio, len(context.containers) / 2)
            context.exec(f'resize set width {context.workspace_width(ratio)}')


class Companion(Layout):

    def __init__(self, workspace_name: str, params: List[Any]):
        super().__init__(LayoutName.COMPANION, workspace_name)
        try:
            self.odd_companion_ratio = float(params[0]) if len(params) > 0 else 0.3
            self.even_companion_ratio = float(params[1]) if len(params) > 1 else 0.4
            self.companion_position = AlternateVerticalPosition(params[2]) \
                if len(params) > 2 else AlternateVerticalPosition.UP
        except ValueError:
            self.odd_companion_ratio = 0.3
            self.even_companion_ratio = 0.4
            self.companion_position = AlternateVerticalPosition.UP
            self._warn_wrong_parameters(params)

    def _params(self) -> List[Any]:
        return [self.odd_companion_ratio, self.even_companion_ratio, self.companion_position.value]

    def anchor_mark(self) -> str:
        return self.mark_last()

    def _update(self, context: Context):
        if len(context.containers) % 2 == 0:
            if (len(context.containers) / 2) % 2 == 1:
                context.exec(f'resize set height {context.workspace_height(self.odd_companion_ratio)}')
            else:
                context.exec(f'resize set height {context.workspace_height(self.even_companion_ratio)}')
            if self.companion_position == AlternateVerticalPosition.UP or \
                    (self.companion_position == AlternateVerticalPosition.ALTUP and
                     (len(context.containers) / 2) % 2 == 1) or \
                    (self.companion_position == AlternateVerticalPosition.ALTDOWN and
                     (len(context.containers) / 2) % 2 == 0):
                context.exec('move up')
            context.exec('split vertical')
        else:
            context.exec('move right')
            context.exec('split vertical')


class ThreeColumns(Layout):

    def __init__(self, workspace_name: str, params: List[Any]):
        super().__init__(LayoutName.THREE_COLUMNS, workspace_name)
        try:
            self.two_columns_main_ratio = float(params[0]) if len(params) > 0 else 0.5
            self.three_columns_main_ratio = float(params[1]) if len(params) > 1 else 0.5
            self.second_column_max = int(params[2]) if len(params) > 2 else 0
            self.second_column_position = HorizontalPosition(params[3]) if len(params) > 3 else HorizontalPosition.LEFT
        except ValueError:
            self.two_columns_main_ratio = 0.5
            self.three_columns_main_ratio = 0.5
            self.second_column_max = 0
            self.second_column_position = HorizontalPosition.LEFT
            self._warn_wrong_parameters(params)

    def _params(self) -> List[Any]:
        return [self.two_columns_main_ratio,
                self.three_columns_main_ratio,
                self.second_column_max,
                self.second_column_position.value]

    def anchor_mark(self) -> str:
        return self.mark_main()

    def _update(self, context: Context):
        if (self.second_column_max == 0 and len(context.containers) % 2 == 0) or \
                len(context.containers) - 1 <= self.second_column_max:
            self._move_to_column(context, 'second')
        else:
            self._move_to_column(context, 'third')

        third_column_container_index = 3 if self.second_column_max == 0 else self.second_column_max + 2
        if len(context.containers) == 1:
            context.exec('split horizontal')
        elif len(context.containers) in [2, third_column_container_index]:
            context.exec('split vertical')

        if len(context.containers) == 2:
            main_width = context.workspace_width(self.two_columns_main_ratio)
            context.exec(f'[con_mark="{self.mark_main()}"] resize set {main_width}')
        elif len(context.containers) == third_column_container_index:
            main_width = context.workspace_width(self.three_columns_main_ratio)
            context.exec(f'[con_mark="{self.mark_main()}"] resize set {main_width}')
            for container in context.containers:
                if self.mark_main() not in container.marks:
                    width = context.workspace_width(self.three_columns_main_ratio / 2)
                    context.exec(f'[con_id="{container.id}"] resize set {width}')

    def _move_to_column(self, context: Context, column: str):
        if (self.second_column_position == HorizontalPosition.RIGHT and column == 'second') or \
                (self.second_column_position == HorizontalPosition.LEFT and column == 'third'):
            context.exec('move right')
        else:
            context.exec('move left')
            context.exec('move left')


class Layouts:
    def __init__(self, layouts: List[Layout] = None):
        if layouts is None:
            layouts = []
        self.layouts = {}
        for layout in layouts:
            self.layouts[layout.workspace_name] = layout

    def get(self, workspace_name: str, default: Layout = None) -> Optional[Layout]:
        return self.layouts[workspace_name] if workspace_name in self.layouts else default

    def add(self, layout: Layout) -> Layout:
        self.layouts[layout.workspace_name] = layout
        return layout

    def remove(self, workspace_name: str):
        if workspace_name in self.layouts:
            del self.layouts[workspace_name]

    def exists_for(self, workspace_name: int) -> bool:
        return workspace_name in self.layouts
