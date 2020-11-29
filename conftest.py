import pytest
from _pytest.nodes import Item
from _pytest.runner import CallInfo
from Xlib import display


def window_to_string(w):
    return f'[{w.get_geometry().x},{w.get_geometry().y}:{w.get_geometry().width}x{w.get_geometry().height}]'


def print_windows_coordinates():
    d = display.Display()
    root = d.screen().root

    query = root.query_tree()
    windows_geometry = [window_to_string(c) for c in query.children
                        if c.get_wm_name() is not None and c.get_wm_name().startswith('[i3 con] container')]
    print(f"\nWindows coordinates:{', '.join(windows_geometry)}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: Item, call: CallInfo):
    outcome = yield
    result = outcome.get_result()
    if result.when == "call" and result.failed:
        try:
            print_windows_coordinates()
        except Exception as e:
            print("Unable to print windows coordinates", e)
            pass
