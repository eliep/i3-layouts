from typing import List, Optional, Any

from i3ipc import Con

from i3l.state import Context


class Layout:
    def __init__(self, layout_name: str, workspace_name: str):
        self.name = layout_name
        self.workspace_name = workspace_name

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
    def create(name: str, params: List[Any], workspace_name: str) -> 'Layout':
        if name == 'vstack':
            return VStack(workspace_name, params)
        elif name == 'hstack':
            return HStack(workspace_name, params)
        elif name == 'spiral':
            return Spiral(workspace_name, params)
        elif name == '3columns':
            return ThreeColumns(workspace_name, params)


class Stack(Layout):
    def __init__(self, layout_name: str, workspace_name: str, params: List[Any]):
        super().__init__(layout_name, workspace_name)
        try:
            self.main_ratio = float(params[0]) if len(params) > 0 else 0.5
            self.second_axe_position = params[1] if len(params) > 1 else self._default_second_axe_position()
        except ValueError:
            self.main_ratio = 0.5
            self.second_axe_position = self._default_second_axe_position()

    def anchor_mark(self) -> str:
        return self.mark_last()

    def _update(self, context: Context):
        if len(context.containers) == 1:
            context.exec(f'split {self._first_direction()}')
        elif len(context.containers) == 2:
            context.exec(f'move {self.second_axe_position}')
            size = context.workspace_width(1 - self.main_ratio) \
                if self._resize_direction() == 'width' else context.workspace_height(1 - self.main_ratio)
            context.exec(f'resize set {self._resize_direction()} {size}')
            context.exec(f'split {self._second_direction()}')

    def _first_direction(self):
        pass

    def _second_direction(self):
        pass

    def _resize_direction(self):
        pass

    def _default_second_axe_position(self):
        pass


class VStack(Stack):

    def __init__(self, workspace_name: str, params: List[Any]):
        super().__init__('vstack', workspace_name, params)

    def _first_direction(self):
        return 'horizontal'

    def _second_direction(self):
        return 'vertical'

    def _resize_direction(self):
        return 'width'

    def _default_second_axe_position(self):
        return 'right'


class HStack(Stack):

    def __init__(self, workspace_name: str, params: List[Any]):
        super().__init__('hstack', workspace_name, params)

    def _first_direction(self):
        return 'vertical'

    def _second_direction(self):
        return 'horizontal'

    def _resize_direction(self):
        return 'height'

    def _default_second_axe_position(self):
        return 'up'


class Spiral(Layout):

    def __init__(self, workspace_name: str, params: List[Any]):
        super().__init__('spiral', workspace_name)
        try:
            self.main_ratio = float(params[0]) if len(params) > 0 else 0.5
        except ValueError:
            self.main_ratio = 0.5

    def anchor_mark(self) -> str:
        return self.mark_last()

    def _update(self, context: Context):
        if len(context.containers) % 2 == 1:
            context.exec('split horizontal')
            if len(context.containers) > 1:
                ratio = pow(1 - self.main_ratio, (len(context.containers) - 1) / 2)
                context.exec(f'resize set height {context.workspace_height(ratio)}')
        else:
            context.exec('split vertical')
            ratio = pow(1 - self.main_ratio, len(context.containers) / 2)
            context.exec(f'resize set width {context.workspace_width(ratio)}')


class ThreeColumns(Layout):

    def __init__(self, workspace_name: str, params: List[Any]):
        super().__init__('3columns', workspace_name)
        try:
            self.two_columns_main_ratio = float(params[0]) if len(params) > 0 else 0.5
            self.three_columns_main_ratio = float(params[1]) if len(params) > 1 else 0.5
            self.second_column_max = int(params[2]) if len(params) > 2 else 0
            self.second_column_position = params[3] if len(params) > 3 else 'left'
        except ValueError:
            self.two_columns_main_ratio = 0.5
            self.three_columns_main_ratio = 0.5
            self.second_column_max = 0
            self.second_column_position = 'left'

    def anchor_mark(self) -> str:
        return self.mark_main()

    def _update(self, context: Context):
        if (self.second_column_max == 0 and len(context.containers) % 2 == 0) or \
                self.second_column_max < len(context.containers) - 1:
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
            context.exec(f'resize set {context.workspace_width(self.three_columns_main_ratio / 2)}')
            context.exec(f'[con_mark="{self.mark_main()}"] resize set {main_width}')

    def _move_to_column(self, context: Context, column: str):
        if (self.second_column_position == 'right' and column == 'second') or \
                (self.second_column_position == 'left' and column == 'third'):
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
