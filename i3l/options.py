from enum import Enum


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

    def opposite(self) -> 'Direction':
        return Direction.HORIZONTAL if self == Direction.VERTICAL else Direction.VERTICAL


class ScreenDirection(Enum):
    INSIDE = 'inside'
    OUTSIDE = 'outside'


class ResizeDirection(Enum):
    WIDTH = 'width'
    HEIGHT = 'height'
