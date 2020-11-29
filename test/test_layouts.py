import logging
import sys
import unittest
from typing import List, Callable

from pytest import approx
from Xlib import X
from Xlib.display import Display
from Xlib.xobject.drawable import Window
from i3ipc import Connection, Event, TickEvent

logging.basicConfig(stream=sys.stdout,
                    format='[%(asctime)s] %(levelname)s {%(filename)s:%(lineno)d} - %(message)s',
                    level=logging.DEBUG)
logger = logging.getLogger(__name__)


class Geom:

    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def __repr__(self):
        return f'@{self.x}:{self.y} {self.width}x{self.height}'


class Workspaces:

    def __init__(self, number_of_workspace: int, current_workspace: int):
        self.number_of_workspace = number_of_workspace
        self.current_workspace = current_workspace
        self.workspace_windows = []
        for i in range(0, number_of_workspace):
            self.workspace_windows.append([])

    def windows(self, workspace_index: int = -1) -> List[Window]:
        return self.workspace_windows[self.current_workspace] if workspace_index == -1 \
            else self.workspace_windows[workspace_index]

    def window(self, index: int, workspace_index: int = -1) -> Window:
        return self.windows(workspace_index)[index]

    def delete_window(self, index: int, workspace_index: int = -1) -> None:
        windows = self.windows(workspace_index)
        del windows[index]

    def move_window(self, index: int, workspace_from: int, workspace_to: int) -> None:
        self.windows(workspace_to).append(self.window(index, workspace_from))
        self.delete_window(index, workspace_from)


class AbstractTestCase:

    @classmethod
    def setup_class(cls):
        cls.display = Display()
        cls.i3 = Connection()
        cls.workspaces = Workspaces(2, 0)

    def _set_layout(self, payload: str):
        self.i3.send_tick('i3-layouts ' + payload)

    def _get_window_geometry(self, window: Window):
        geom = window.get_geometry()
        (x, y) = (geom.x, geom.y)
        while True:
            parent = window.query_tree().parent
            parent_geom = parent.get_geometry()
            x += parent_geom.x
            y += parent_geom.y
            if parent.id == self.display.screen().root.id:
                break
            window = parent
        return Geom(x, y, geom.width, geom.height)

    def _rebuild_command(self, command: Callable[[], None], rebuild_cause: str):
        def on_tick(i3l: Connection, e: TickEvent):
            token = e.payload.split(' ')
            if not e.first and e.payload.startswith('i3-layouts rebuild') and token[-1] == rebuild_cause:
                i3l.off(on_tick)
                i3l.main_quit()
            elif e.first:
                command()
                self.display.sync()

        self.display.sync()
        i3 = Connection()
        i3.on(Event.TICK, on_tick)
        i3.main()
        self.display.sync()

    def _close_all(self):
        def flat_map(f: Callable, xs: List[List]) -> List:
            return [y for ys in xs for y in f(ys)]
        windows = flat_map(lambda workspace: workspace, self.workspaces.workspace_windows)
        p = {'remaining_window_count': len(windows)}

        def on_tick(i3l: Connection, e: TickEvent):
            if not e.first and e.payload == 'i3-layouts rebuild window_close':
                p['remaining_window_count'] -= 1
                if p['remaining_window_count'] == 0:
                    i3l.main_quit()
            elif e.first:
                for window in windows:
                    window.destroy()
                self.display.sync()

        self.display.sync()
        i3 = Connection()
        i3.on(Event.TICK, on_tick)
        i3.main()
        self.workspaces = Workspaces(2, 0)

    def _create_windows(self) -> None:
        def command():
            screen = self.display.screen()
            window = screen.root.create_window(
                10, 10, 100, 100, 0,
                screen.root_depth,
                background_pixel=screen.white_pixel,
                event_mask=X.ExposureMask | X.KeyPressMask)
            window.map()
            self.workspaces.windows().append(window)

        self._rebuild_command(command, 'window_new')

    def _create_moving_windows(self, workspace_to: int, window_class: str = '') -> None:
        def command():
            if window_class != '':
                self.workspaces.window(-1).set_wm_class('x', window_class)

        self._create_windows()
        self._rebuild_command(command, 'window_move')
        self.workspaces.move_window(-1, 0, workspace_to)

    def _close_window(self, index: int) -> None:
        def command():
            self.workspaces.window(index).destroy()

        self._rebuild_command(command, 'window_close')
        self.workspaces.delete_window(index)

    def _move_window_to_workspace(self, index: int, workspace_to: int) -> None:
        def command():
            self.i3.command(f'[id="{self.workspaces.window(index).id}"] focus')
            self.i3.command(f'move container to workspace {workspace_to + 1}')

        self._rebuild_command(command, 'window_move')
        self.workspaces.move_window(index, self.workspaces.current_workspace, workspace_to)

    def _move_window_from_workspace(self, workspace_from: int) -> None:
        def set_hstack_layout():
            self.i3.send_tick('i3-layouts hstack')

        def move_to_workspace():
            self.i3.command(f'move container to workspace 1')

        def switch_workspace(workspace_number: int) -> Callable[[], None]:
            def _switch_workspace():
                self.i3.command(f'workspace {workspace_number}')
            return _switch_workspace

        self._rebuild_command(switch_workspace(workspace_from + 1), 'workspace_focus')
        self._rebuild_command(set_hstack_layout, 'layout_change_hstack')
        self._rebuild_command(move_to_workspace, 'window_move')
        self._rebuild_command(switch_workspace(1), 'workspace_focus')
        self.workspaces.move_window(0, workspace_from, self.workspaces.current_workspace)

    def _switch_layout(self, origin_layout: str, target_layout_name: str) -> None:
        def set_origin_layout():
            self._set_layout(f'{origin_layout}')

        def set_target_layout():
            self._set_layout(f'{target_layout_name}')

        origin_layout_name = origin_layout.split(' ')[0]
        self._rebuild_command(set_target_layout, f'layout_change_{target_layout_name}')
        self._rebuild_command(set_origin_layout, f'layout_change_{origin_layout_name}')

    def wait_for_quit(self):
        do_quit = False
        while not do_quit:
            x = self.display.next_event()
            if x.type == X.KeyPress and x.detail == 38:
                do_quit = True


class I3LayoutScenario(AbstractTestCase):

    def senario(self, params: List):
        layout = self.layout(params)
        self._set_layout(layout)
        logger.debug(f'=== test {layout} create 6 windows from scratch ===')
        for i in range(0, 6):
            self._create_windows()
        self.validate(params)

        logger.debug(f'=== test {layout} close first window ===')
        self._close_window(0)
        self.validate(params)

        logger.debug(f'=== test {layout} close last window ===')
        self._close_window(len(self.workspaces.windows()) - 1)
        self.validate(params)

        logger.debug(f'=== test {layout} create 3 windows ===')
        for i in range(0, 3):
            self._create_windows()
        self.validate(params)

        logger.debug(f'=== test {layout} move one window to another workspace ===')
        self._move_window_to_workspace(3, 1)
        self.validate(params)

        logger.debug(f'=== test {layout} move one window from another workspace ===')
        self._move_window_from_workspace(1)
        self.validate(params)

        logger.debug(f'=== test {layout} switch layout ===')
        self._switch_layout(layout, self.alternate_layout())
        self.validate(params)

        logger.debug(f'=== test {layout} create windows moved to another workspace ===')
        self._create_moving_windows(1, window_class='move-window')
        self.validate(params)
        # self.wait_for_quit()

    def validate(self, params: List):
        pass

    def layout(self, params: List) -> str:
        pass

    def layout_params(self) -> List:
        pass

    def alternate_layout(self) -> str:
        pass


class TestHStack(I3LayoutScenario):

    def test_scenario(self):
        for params in self.layout_params():
            self.senario(params)
            self._close_all()

    def layout(self, params: List) -> str:
        ratio, position = params
        return f'hstack {ratio} {position}'

    def layout_params(self) -> List:
        return [[0.6, 'up']]

    def alternate_layout(self) -> str:
        return 'vstack'

    def validate(self, args):
        ratio, position = args
        windows = self.workspaces.windows()
        geoms = [self._get_window_geometry(window) for window in windows]
        print(geoms)

        first = geoms[0]
        master_height = 800 * ratio - 2
        assert first.height == master_height

        last = geoms[-1]
        stack_height = 800 * (1 - ratio) - 2
        assert last.height == approx(stack_height, abs=1)

        for i, geom in enumerate(geoms[1:]):
            if position == 'down':
                assert geom.y > first.y + first.height
            elif position == 'up':
                assert geom.y < first.y + first.height

            if i + 1 < len(geoms) - 1:
                assert geom.x + geom.width < geoms[i+2].x
                assert geom.width == approx(geoms[i + 2].width, abs=1)


class TestVStack(I3LayoutScenario):

    def test_scenario(self):
        for params in self.layout_params():
            self.senario(params)
            self._close_all()

    def layout(self, params: List) -> str:
        ratio, position = params
        return f'vstack {ratio} {position}'

    def layout_params(self) -> List:
        return [
            [0.6, 'right'],
            [0.4, 'left']
        ]

    def alternate_layout(self) -> str:
        return 'hstack'

    def validate(self, args):
        ratio, position = args
        windows = self.workspaces.windows()
        geoms = [self._get_window_geometry(window) for window in windows]

        first = geoms[0]
        master_width = 1280 * ratio - 2
        assert first.width == master_width

        last = geoms[-1]
        stack_width = 1280 * (1 - ratio) - 2
        assert last.width == approx(stack_width, abs=1)

        for i, geom in enumerate(geoms[1:]):
            if position == 'right':
                assert geom.x > first.x + first.width
            elif position == 'left':
                assert geom.x < first.x + first.width

            if i + 1 < len(geoms) - 1:
                assert geom.y + geom.height < geoms[i+2].y
                assert geom.height == approx(geoms[i + 2].height, abs=1)


class TestSpiral(I3LayoutScenario):

    def test_scenario(self):
        for params in self.layout_params():
            self.senario(params)
            self._close_all()

    def layout(self, params: List) -> str:
        ratio, direction = params
        return f'spiral {ratio} {direction}'

    def layout_params(self) -> List:
        return [[0.6, 'outside']]

    def alternate_layout(self) -> str:
        return 'hstack'

    def validate(self, args):
        ratio, direction = args
        windows = self.workspaces.windows()
        geoms = [self._get_window_geometry(window) for window in windows]

        for i, geom in enumerate(geoms[1:]):
            prev_geom = geoms[i]
            if i % 2 == 0:
                assert geom.x > prev_geom.x + prev_geom.width
                assert geom.width == approx((1 - ratio) * (prev_geom.width + geom.width), abs=2)
            else:
                assert geom.y > prev_geom.y + prev_geom.height
                assert geom.height == approx((1 - ratio) * (prev_geom.height + geom.height), abs=2)


class TestCompanion(I3LayoutScenario):

    def test_scenario(self):
        for params in self.layout_params():
            self.senario(params)
            self._close_all()

    def layout(self, params: List) -> str:
        odd_companion_ratio, even_companion_ratio, companion_position = params
        return f'companion {odd_companion_ratio} {even_companion_ratio} {companion_position}'

    def layout_params(self) -> List:
        return [[0.3, 0.4, 'up']]

    def alternate_layout(self) -> str:
        return 'hstack'

    def validate(self, args):
        odd_ratio, even_ratio, companion_position = args
        windows = self.workspaces.windows()
        geoms = [self._get_window_geometry(window) for window in windows]

        for i, geom in enumerate(geoms[0::2]):
            if len(geoms) % 2 == 0 or i*2+1 < len(geoms):
                prev_geom = geoms[i*2+1]
                assert geom.x == prev_geom.x
                assert geom.y > prev_geom.y + prev_geom.height
                ratio = odd_ratio if i % 2 == 0 else even_ratio
                assert geom.height == approx((1 - ratio) * (prev_geom.height + geom.height), abs=2)
            else:
                assert geom.height == approx(800, abs=2)
            if i > 0:
                assert geom.x > geoms[(i-1)*2].x


class TestThreeColumns(I3LayoutScenario):

    def test_scenario(self):
        for params in self.layout_params():
            self.senario(params)
            self._close_all()

    def layout(self, params: List) -> str:
        ratio_2, ratio_3, max_2, position_2 = params
        return f'3columns {ratio_2} {ratio_3} {max_2} {position_2}'

    def layout_params(self) -> List:
        return [
            [0.66, 0.5, 2, 'left'],
            [0.66, 0.5, 2, 'right'],
            [0.66, 0.5, 0, 'left']
        ]

    def alternate_layout(self) -> str:
        return 'hstack'

    def validate(self, args):
        ratio_2, ratio_3, max_2, position_2 = args
        windows = self.workspaces.windows()
        geoms = [self._get_window_geometry(window) for window in windows]

        main = geoms[0]
        column_2, column_3 = (geoms[1:max_2+1], geoms[max_2+1:]) if max_2 > 0 else (geoms[1::2], geoms[2::2])

        for i, geom in enumerate(column_2):
            if i > 0:
                assert geom.height == approx(column_2[i-1].height, abs=1)
            if position_2 == 'left':
                assert geom.x < main.x
            else:
                assert geom.x > main.x

        for i, geom in enumerate(column_3):
            if i > 0:
                assert geom.height == approx(column_3[i-1].height, abs=1)
            if position_2 == 'left':
                assert geom.x > main.x
            else:
                assert geom.x < main.x

        if len(geoms) > max_2 + 1:
            column_2_width = column_2[0].width
            column_3_width = column_3[0].width
            assert column_2_width == approx(column_3_width, abs=2)
            assert main.width == approx(ratio_3 * (main.width + column_2_width + column_3_width), abs=2)
        elif len(geoms) > 1:
            column_2_width = column_2[0].width
            assert main.width == approx(ratio_2 * (main.width + column_2_width), abs=2)


class TestTwoColumns(I3LayoutScenario):

    def test_scenario(self):
        for params in self.layout_params():
            self.senario(params)
            self._close_all()

    def layout(self, params: List) -> str:
        position = params[0]
        return f'2columns {position}'

    def layout_params(self) -> List:
        return [['left']]

    def alternate_layout(self) -> str:
        return 'hstack'

    def validate(self, args):
        windows = self.workspaces.windows()
        geoms = [self._get_window_geometry(window) for window in windows]

        column_1, column_2 = geoms[::2], geoms[1::2]

        for i, geom in enumerate(column_1[1:]):
            assert geom.height == approx(column_1[i].height, abs=1)
            assert geom.y > column_1[i].y + column_1[i].height
            assert geom.x == column_1[i].x
            if len(column_2) > 0:
                assert geom.x < column_2[0].x

        for i, geom in enumerate(column_2[1:]):
            assert geom.height == approx(column_2[i].height, abs=1)
            assert geom.y > column_2[i].y + column_2[i].height
            assert geom.x == column_2[i].x


if __name__ == '__main__':
    unittest.main()
