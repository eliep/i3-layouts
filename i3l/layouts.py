import logging
import sys
from math import sqrt
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
    TWO_COLUMNS = '2columns'
    COMPANION = 'companion'
    TABBED = 'tabbed'
    SPLITV = 'splitv'
    SPLITH = 'splith'
    STACKING = 'stacking'


class HorizontalPosition(Enum):
    RIGHT = 'right'
    LEFT = 'left'

    def opposite(self) -> 'HorizontalPosition':
        return HorizontalPosition.RIGHT if self == HorizontalPosition.LEFT else HorizontalPosition.LEFT


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

    def is_i3(self) -> bool:
        return False

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

        self._update(context)
        mark = self.mark_main() if len(containers) == 1 else self.mark_last()
        context.exec(f'mark {mark}')

    def _update(self, context: Context):
        pass

    @classmethod
    def move(cls, context: Context, direction: str):
        origin = context.focused
        candidates = cls._destination_candidates(context, direction, origin)
        destination = cls._shortest_distance(origin, candidates)
        if destination is not None:
            cls._switch_marks(context, origin, destination)
            cls._switch_window_numbers(context, origin, destination)
            context.exec(f'swap container with con_id {destination.id}')

    @classmethod
    def _destination_candidates(cls, context: Context, direction: str, origin: Con) -> List[Con]:
        def vertical_overlap(origin: Con, candidate: Con):
            return candidate.rect.y <= origin.rect.y <= candidate.rect.y + candidate.rect.height \
                or candidate.rect.y <= origin.rect.y + origin.rect.height <= candidate.rect.y + candidate.rect.height

        def horizontal_overlap(origin: Con, candidate: Con):
            return candidate.rect.x <= origin.rect.x <= candidate.rect.x + candidate.rect.width \
                or candidate.rect.x <= origin.rect.x + origin.rect.width < candidate.rect.x + candidate.rect.width

        def overlap(direction: str):
            return horizontal_overlap if direction in ['up', 'down'] else vertical_overlap

        factor = -1 if direction in ['right', 'down'] else 1

        candidates = []
        if direction in ['left', 'right']:
            candidates = [con for con in context.containers
                          if factor * con.rect.x < factor * origin.rect.x and overlap(direction)(origin, con)]
        elif direction in ['up', 'down']:
            candidates = [con for con in context.containers
                          if factor * con.rect.y < factor * origin.rect.y and overlap(direction)(origin, con)]
        return candidates

    @classmethod
    def _switch_marks(cls, context: Context, origin: Con, destination: Con):
        origin_marks = [mark for mark in origin.marks if mark.startswith('i3l')]
        for mark in destination.marks:
            if mark.startswith('i3l'):
                context.exec(f'[con_id="{origin.id}"] mark {mark}')
        for mark in origin_marks:
            context.exec(f'[con_id="{destination.id}"] mark {mark}')

    @classmethod
    def _switch_window_numbers(cls, context: Context, origin: Con, destination: Con):
        numbers = context.workspace_sequence.window_numbers
        for con_id, number in numbers.items():
            if con_id == origin.id:
                numbers[destination.id] = number
            elif con_id == destination.id:
                numbers[origin.id] = number

    @classmethod
    def _shortest_distance(cls, origin: Con, containers: List[Con]) -> Optional[Con]:
        shortest_dist = sys.maxsize
        destination = None
        for con in containers:
            dist = cls.container_distance(origin, con)
            if dist < shortest_dist and not (origin.rect.x == con.rect.x and origin.rect.y == con.rect.y):
                destination = con
                shortest_dist = dist
        return destination

    @staticmethod
    def container_distance(con1: Con, con2: Con) -> float:
        return sqrt((con1.rect.x - con2.rect.x)**2 + (con1.rect.y - con2.rect.y)**2)

    @classmethod
    def create(cls, workspace_name: str, params: List[Any]) -> Optional['Layout']:
        pass


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
            context.exec(f'[con_id="{context.focused.id}"] move {self.second_axe_position.value}')
            context.exec(f'[con_id="{context.focused.id}"] move {self.second_axe_position.value}')
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

    @classmethod
    def create(cls, workspace_name: str, params: List[Any]) -> Optional['Layout']:
        return VStack(workspace_name, params)


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

    @classmethod
    def create(cls, workspace_name: str, params: List[Any]) -> Optional['Layout']:
        return HStack(workspace_name, params)


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
                context.exec(f'[con_id="{context.focused.id}"] move up')
            context.exec('split horizontal')
            if len(context.containers) > 1:
                ratio = pow(1 - self.main_ratio, (len(context.containers) - 1) / 2)
                context.exec(f'resize set height {context.workspace_height(ratio)}')
        else:
            if self.screen_direction == ScreenDirection.INSIDE and (len(context.containers) / 2) % 2 == 0:
                context.exec(f'[con_id="{context.focused.id}"] move left')
            context.exec('split vertical')
            ratio = pow(1 - self.main_ratio, len(context.containers) / 2)
            context.exec(f'resize set width {context.workspace_width(ratio)}')

    @classmethod
    def create(cls, workspace_name: str, params: List[Any]) -> Optional['Layout']:
        return Spiral(workspace_name, params)


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
            if self.should_moves_up(context):
                context.exec(f'[con_id="{context.focused.id}"] move up')
            context.exec('split vertical')
        else:
            context.exec(f'[con_id="{context.focused.id}"] move right')
            context.exec('split vertical')

    def should_moves_up(self, ctx: Context) -> bool:
        return self.companion_position == AlternateVerticalPosition.UP or \
            (self.companion_position == AlternateVerticalPosition.ALTUP and (len(ctx.containers) / 2) % 2 == 1) or \
            (self.companion_position == AlternateVerticalPosition.ALTDOWN and (len(ctx.containers) / 2) % 2 == 0)

    @classmethod
    def create(cls, workspace_name: str, params: List[Any]) -> Optional['Layout']:
        return Companion(workspace_name, params)


class TwoColumns(Layout):

    def __init__(self, workspace_name: str, params: List[Any]):
        super().__init__(LayoutName.TWO_COLUMNS, workspace_name)
        try:
            self.first_column_position = HorizontalPosition(params[0]) if len(params) > 0 else HorizontalPosition.LEFT
        except ValueError:
            self.first_column_position = HorizontalPosition.LEFT
            self._warn_wrong_parameters(params)
        self.second_column_position = self.first_column_position.opposite()

    def _params(self) -> List[Any]:
        return []

    def anchor_mark(self) -> str:
        return self.mark_main()

    def _update(self, context: Context):
        if len(context.containers) <= 2:
            context.exec(f'[con_id="{context.focused.id}"] move {self.second_column_position.value}')
            context.exec('split vertical')
            return

        sorted_containers = context.sorted_containers()
        candidates = sorted_containers[1:-1:2] if len(context.containers) % 2 == 0 else sorted_containers[:-1:2]
        self._move_container_to_lowest(context, candidates)

    def _move_container_to_lowest(self, context: Context, candidates: List[Con]):
        lowest_mark = 'i3l:lowest'
        lowest = self._lowest(candidates)
        if lowest is not None:
            context.exec(f'[con_id="{lowest.id}"] mark --add {lowest_mark}')
        context.exec(f'move container to mark {lowest_mark}')
        context.exec(f'unmark {lowest_mark}')

    @classmethod
    def _lowest(cls, containers: List[Con]) -> Optional[Con]:
        lower_y = 0
        destination = None
        for con in containers:
            if con.rect.y >= lower_y:
                destination = con
                lower_y = con.rect.y
        return destination

    @classmethod
    def create(cls, workspace_name: str, params: List[Any]) -> Optional['Layout']:
        return TwoColumns(workspace_name, params)


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
            containers = context.resync().sorted_containers()
            stack_width = context.workspace_width((1 - self.three_columns_main_ratio) / 2)
            stack_width_delta = containers[1].rect.width - stack_width
            self._resize(context, 'con_id', containers[1].id, stack_width_delta)
            main_width = context.workspace_width(self.three_columns_main_ratio)
            main_width_delta = containers[0].rect.width + stack_width_delta - main_width
            self._resize(context, 'con_mark', self.mark_main(), main_width_delta)

    def _resize(self, context: Context, attr: str, value: str, delta: int):
        resize_direction = self.second_column_position.opposite().value
        resize_expansion = 'shrink' if delta >= 0 else 'grow'
        context.exec(f'[{attr}="{value}"] resize {resize_expansion} {resize_direction} {abs(delta)} px')

    def _move_to_column(self, context: Context, column: str):
        if (self.second_column_position == HorizontalPosition.RIGHT and column == 'second') or \
                (self.second_column_position == HorizontalPosition.LEFT and column == 'third'):
            context.exec(f'[con_id="{context.focused.id}"] move right')
        else:
            context.exec(f'[con_id="{context.focused.id}"] move left')
            context.exec(f'[con_id="{context.focused.id}"] move left')

    @classmethod
    def create(cls, workspace_name: str, params: List[Any]) -> Optional['Layout']:
        return ThreeColumns(workspace_name, params)


class I3Layout(Layout):

    def __init__(self, layout_name: LayoutName, workspace_name: str):
        super().__init__(layout_name, workspace_name)

    def _params(self) -> List[Any]:
        return []

    def is_i3(self) -> bool:
        return True

    def anchor_mark(self) -> str:
        return self.mark_main()

    def _update(self, context: Context):
        context.exec(f'layout {self.name.value}')


class Tabbed(I3Layout):

    def __init__(self, workspace_name: str):
        super().__init__(LayoutName.TABBED, workspace_name)

    @classmethod
    def create(cls, workspace_name: str, params: List[Any]) -> Optional['Layout']:
        return Tabbed(workspace_name)


class SplitV(I3Layout):

    def __init__(self, workspace_name: str):
        super().__init__(LayoutName.SPLITV, workspace_name)

    @classmethod
    def create(cls, workspace_name: str, params: List[Any]) -> Optional['Layout']:
        return SplitV(workspace_name)


class SplitH(I3Layout):

    def __init__(self, workspace_name: str):
        super().__init__(LayoutName.SPLITH, workspace_name)

    @classmethod
    def create(cls, workspace_name: str, params: List[Any]) -> Optional['Layout']:
        return SplitH(workspace_name)


class Stacking(I3Layout):

    def __init__(self, workspace_name: str):
        super().__init__(LayoutName.STACKING, workspace_name)

    @classmethod
    def create(cls, workspace_name: str, params: List[Any]) -> Optional['Layout']:
        return Stacking(workspace_name)


class Layouts:
    factory = {
        LayoutName.VSTACK: VStack,
        LayoutName.HSTACK: HStack,
        LayoutName.SPIRAL: Spiral,
        LayoutName.TWO_COLUMNS: TwoColumns,
        LayoutName.THREE_COLUMNS: ThreeColumns,
        LayoutName.COMPANION: Companion,
        LayoutName.TABBED: Tabbed,
        LayoutName.SPLITV: SplitV,
        LayoutName.SPLITH: SplitH,
        LayoutName.STACKING: Stacking,
    }

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

    def exists_for(self, workspace_name: str) -> bool:
        return workspace_name in self.layouts

    @classmethod
    def create(cls, name: str, params: List[Any], workspace_name: str) -> Optional['Layout']:
        try:
            layout_name = LayoutName(name)
            return cls.factory[layout_name].create(workspace_name, params) if layout_name in cls.factory else None
        except ValueError:
            logger.error(f'[layouts] Invalid layout name: {name}. Skipping')
            return None
