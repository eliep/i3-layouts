import logging
from typing import List, Optional, Any, Union

from i3ipc import Con

from i3l.corners import Corners
from i3l.mover import Mover
from i3l.options import LayoutName, Direction, ResizeDirection, HorizontalPosition, VerticalPosition, ScreenDirection, \
    AlternateVerticalPosition
from i3l.splitter import Splittable, Splitter
from i3l.state import Context

logger = logging.getLogger(__name__)


class Layout(Splittable):
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

    def anchor_mark(self) -> Optional[str]:
        pass

    def get_workspace_name(self):
        return self.workspace_name

    def split_direction(self, context: Context) -> Optional[Direction]:
        return None

    def stack_direction(self, context: Context) -> Optional[Direction]:
        return None

    def update(self, context: Context, con: Con):
        Splitter(context).handle_split(self)

        containers = context.containers
        if len(containers) > 1 and self.anchor_mark() is not None:
            context.exec(f'[con_id="{con.id}"] move window to mark {self.anchor_mark()}')
            context.resync()

        self._update(context)

        context.exec(f'mark {self.mark_last()}')
        if len(containers) == 1:
            context.exec(f'mark --add {self.mark_main()}')

    def _update(self, context: Context):
        pass

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

    def anchor_mark(self) -> Optional[str]:
        return self.mark_last()

    def split_direction(self, context: Context) -> Optional[Direction]:
        if len(context.containers) == 2:
            return self._first_direction()
        elif len(context.containers) == 3:
            return self._second_direction()
        else:
            return None

    def stack_direction(self, context: Context) -> Optional[Direction]:
        return self._first_direction().opposite()

    # def _split_indices(self):
    #     return [1, 2]
    #
    # def _split_direction(self, context: Context):
    #     return self._first_direction().value if len(context.containers) == 1 else self._second_direction().value

    def _update(self, context: Context):
        # if len(context.containers) == 1:
        #     context.exec(f'split {self._first_direction().value}')
        # el
        if len(context.containers) == 2:
            context.exec(f'[con_id="{context.focused.id}"] move {self.second_axe_position.value}')
            context.exec(f'[con_id="{context.focused.id}"] move {self.second_axe_position.value}')
            size = context.workspace_width(1 - self.main_ratio) \
                if self._resize_direction() == ResizeDirection.WIDTH else context.workspace_height(1 - self.main_ratio)
            context.exec(f'resize set {self._resize_direction().value} {size}')
            # context.exec(f'split {self._second_direction().value}')

    def _first_direction(self) -> Direction:
        pass

    def _second_direction(self) -> Direction:
        return self._first_direction().opposite()

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

    def anchor_mark(self) -> Optional[str]:
        return self.mark_last()

    def split_direction(self, context: Context) -> Optional[Direction]:
        return Direction.HORIZONTAL if len(context.containers) % 2 == 0 else Direction.VERTICAL

    def _update(self, context: Context):
        if len(context.containers) % 2 == 1:
            if self.screen_direction == ScreenDirection.INSIDE and ((len(context.containers) - 1) / 2) % 2 == 0:
                context.exec(f'[con_id="{context.focused.id}"] move up')
            if len(context.containers) > 1:
                ratio = pow(1 - self.main_ratio, (len(context.containers) - 1) / 2)
                context.exec(f'resize set height {context.workspace_height(ratio)}')
        else:
            if self.screen_direction == ScreenDirection.INSIDE and (len(context.containers) / 2) % 2 == 0:
                context.exec(f'[con_id="{context.focused.id}"] move left')
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

    def anchor_mark(self) -> Optional[str]:
        return self.mark_last()

    def split_direction(self, context: Context) -> Optional[Direction]:
        return Direction.VERTICAL if len(context.containers) % 2 == 0 else None

    def _update(self, context: Context):
        if len(context.containers) % 2 == 0:
            if (len(context.containers) / 2) % 2 == 1:
                context.exec(f'resize set height {context.workspace_height(self.odd_companion_ratio)}')
            else:
                context.exec(f'resize set height {context.workspace_height(self.even_companion_ratio)}')
            if self.should_moves_up(context):
                context.exec(f'[con_id="{context.focused.id}"] move up')
        else:
            context.exec(f'[con_id="{context.focused.id}"] move right')
            context.exec(f'[con_id="{context.focused.id}"] move right')

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

    def anchor_mark(self) -> Optional[str]:
        return self.mark_main()

    def split_direction(self, context: Context) -> Optional[Direction]:
        return Direction.VERTICAL if len(context.containers) <= 3 else None

    def stack_direction(self, context: Context) -> Optional[Direction]:
        return Direction.VERTICAL

    def _update(self, context: Context):
        if len(context.containers) <= 2:
            context.exec(f'[con_id="{context.focused.id}"] move {self.second_column_position.value}')
            return

        sorted_containers = context.sorted_containers()
        candidates = sorted_containers[1:-1:2] if len(context.containers) % 2 == 0 else sorted_containers[:-1:2]
        self._move_container_to_lowest(context, candidates)

    def _move_container_to_lowest(self, context: Context, candidates: List[Con]):
        lowest = self._lowest(candidates)
        if lowest is not None:
            Mover(context).move_to_container(lowest.id)

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

    def anchor_mark(self) -> Optional[str]:
        return self.mark_last()

    def split_direction(self, context: Context) -> Optional[Direction]:
        third_column_container_index = 3 if self.second_column_max == 0 else self.second_column_max + 2
        return Direction.VERTICAL if len(context.containers) in [2, 3, third_column_container_index + 1] else None

    def stack_direction(self, context: Context) -> Optional[Direction]:
        return Direction.VERTICAL

    def _update(self, context: Context):
        is_second_column = (self.second_column_max == 0 and len(context.containers) % 2 == 0) or \
            len(context.containers) - 1 <= self.second_column_max
        is_right = (self.second_column_position == HorizontalPosition.RIGHT and is_second_column) or \
                   (self.second_column_position == HorizontalPosition.LEFT and not is_second_column)
        third_column_container_index = 3 if self.second_column_max == 0 else self.second_column_max + 2

        corners = Corners(context.containers)
        bottom_container = corners.bottom_right() if is_right else corners.bottom_left()
        direction = None if len(context.containers) not in [2, third_column_container_index] \
            else 'right' if is_right else 'left'
        Mover(context).move_to_container(bottom_container.id, direction)

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

    def anchor_mark(self) -> Optional[str]:
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
