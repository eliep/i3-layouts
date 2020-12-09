from typing import List, Optional

from i3ipc import Con


class Corners:
    def __init__(self, containers: List[Con]):
        self._containers = containers
        self.xs = list(dict.fromkeys([container.rect.x for container in self._containers]))
        self.xs.sort()
        self.ys = list(dict.fromkeys([container.rect.y for container in self._containers]))
        self.ys.sort()
        self.left = self.xs[0]
        self.top = self.ys[0]
        self.right = max([container.rect.x + container.rect.width for container in self._containers])
        self.bottom = max([container.rect.y + container.rect.height for container in self._containers])

    def top_left(self) -> Optional[Con]:
        for container in self._containers:
            if container.rect.x == self.left and container.rect.y == self.top:
                return container
        return None

    def bottom_left(self) -> Optional[Con]:
        for container in self._containers:
            if container.rect.x == self.left and container.rect.y + container.rect.height == self.bottom:
                return container
        return None

    def bottom_right(self) -> Optional[Con]:
        for container in self._containers:
            if container.rect.x + container.rect.width == self.right and \
                    container.rect.y + container.rect.height == self.bottom:
                return container
        return None

    def top_right(self) -> Optional[Con]:
        for container in self._containers:
            if container.rect.x + container.rect.width == self.right and container.rect.y == self.top:
                return container
        return None
