import sys
from math import sqrt
from typing import List, Optional

from i3ipc import Con

from i3l.splitter import Mark
from i3l.state import Context


class Mover:

    def __init__(self, context: Context):
        self._context = context

    def forward(self, direction: str):
        self._context.exec(f'move {direction}')

    def move_to_container(self, con_id: int, direction: Optional[str] = None):
        temp_mark = 'i3l:temp'
        if self._context.focused.id != con_id:
            self._context.exec(f'[con_id="{con_id}"] mark --add {temp_mark}')
            self._context.exec(f'move container to mark {temp_mark}')
            self._context.exec(f'unmark {temp_mark}')
        if direction is not None:
            self._context.exec(f'move {direction}')

    def move_to_direction(self, direction: str, swap_mark_last: bool):
        origin = self._context.focused
        candidates = self._destination_candidates(direction, origin)
        destination = self._shortest_distance(origin, candidates)
        if destination is not None:
            self.swap(destination, swap_mark_last)

    def swap(self, destination: Con, swap_mark_last: bool, swap_marks=None):
        if swap_marks is None:
            swap_marks = []
        self._switch_marks(destination, swap_mark_last, swap_marks)
        if self._context.workspace_sequence is not None:
            self._context.workspace_sequence.switch_container_order(self._context.focused, destination)
        self._context.exec(f'swap container with con_id {destination.id}')

    def _destination_candidates(self, direction: str, origin: Con) -> List[Con]:
        def vertical_overlap(candidate: Con):
            return candidate.rect.y <= origin.rect.y <= candidate.rect.y + candidate.rect.height \
                or candidate.rect.y <= origin.rect.y + origin.rect.height <= candidate.rect.y + candidate.rect.height

        def horizontal_overlap(candidate: Con):
            return candidate.rect.x <= origin.rect.x <= candidate.rect.x + candidate.rect.width \
                or candidate.rect.x <= origin.rect.x + origin.rect.width < candidate.rect.x + candidate.rect.width

        def overlap():
            return horizontal_overlap if direction in ['up', 'down'] else vertical_overlap

        factor = -1 if direction in ['right', 'down'] else 1

        candidates = []
        if direction in ['left', 'right']:
            candidates = [con for con in self._context.containers
                          if factor * con.rect.x < factor * origin.rect.x and overlap()(con)]
        elif direction in ['up', 'down']:
            candidates = [con for con in self._context.containers
                          if factor * con.rect.y < factor * origin.rect.y and overlap()(con)]
        return candidates

    def _switch_marks(self, destination: Con, swap_mark_last: bool, swap_marks=None):
        if swap_marks is None:
            swap_marks = []
        origin_mark = [mark for mark in self._context.focused.marks]
        mark_to_swap = [Mark.MAIN, Mark.LAST] + swap_marks if swap_mark_last else [Mark.MAIN] + swap_marks
        for mark in destination.marks:
            if Mark.any(mark, mark_to_swap):
                self._context.exec(f'[con_id="{self._context.focused.id}"] mark --add {mark}')
            if not Mark.belongs_to(mark, self._context.workspace.name):
                self._context.exec(f'[con_id="{destination.id}"] unmark {mark}')
        for mark in origin_mark:
            if Mark.any(mark, mark_to_swap):
                self._context.exec(f'[con_id="{destination.id}"] mark --add {mark}')

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
