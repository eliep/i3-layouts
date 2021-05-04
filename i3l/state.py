import logging
import shlex
import subprocess
from enum import Enum
from typing import Dict, List, Optional

from i3ipc import Con, Connection, CommandReply, TickReply

logger = logging.getLogger(__name__)


def is_floating_container(container: Con) -> bool:
    return container.floating == 'auto_on' or container.floating == 'user_on'


def is_layout_container(container: Con) -> bool:
    return container.window is not None and container.type == 'con' and not is_floating_container(container)


class RebuildCause(Enum):
    LAYOUT_CHANGE_VSTACK = 'layout_change_vstack'
    LAYOUT_CHANGE_HSTACK = 'layout_change_hstack'
    LAYOUT_CHANGE_SPIRAL = 'layout_change_spiral'
    LAYOUT_CHANGE_COMPANION = 'layout_change_companion'
    LAYOUT_CHANGE_2COLUMNS = 'layout_change_2columns'
    LAYOUT_CHANGE_3COLUMNS = 'layout_change_3columns'
    LAYOUT_CHANGE_TABBED = 'layout_change_tabbed'
    LAYOUT_CHANGE_AUTOSPLIT = 'layout_change_autosplit'
    WORKSPACE_FOCUS = 'workspace_focus'
    WINDOW_CLOSE = 'window_close'
    WINDOW_MOVE = 'window_move'
    WINDOW_NEW = 'window_new'

    @staticmethod
    def layout_change(layout_name: str) -> 'RebuildCause':
        return RebuildCause(f'layout_change_{layout_name}')


class WorkspaceSequence:
    def __init__(self):
        self._container_count = 0
        self._container_orders: Dict[int, int] = {}
        self.is_stale = False
        self.stale_con_id = 0

    def contains(self, con_id: int):
        return con_id in self._container_orders

    def set_order(self, container: Con):
        self._container_count += 1
        self._container_orders[container.id] = self._container_count

    def get_order(self, con_id: int) -> Optional[int]:
        return self._container_orders[con_id] if con_id in self._container_orders else None

    def switch_container_order(self, origin: Con, destination: Con):
        origin_number = destination_number = None
        for con_id, number in self._container_orders.items():
            if con_id == origin.id:
                origin_number = number
            elif con_id == destination.id:
                destination_number = number
        self._container_orders[destination.id] = origin_number
        self._container_orders[origin.id] = destination_number

    def set_stale(self, stale: bool, con_id: int = 0):
        self.is_stale = stale
        if con_id == 0 or \
                self.stale_con_id == 0 or \
                self._container_orders[con_id] < self._container_orders[self.stale_con_id]:
            self.stale_con_id = con_id


class RebuildContainer:

    def __init__(self, container: Con):
        self.window = container.window
        self.x = container.geometry.x
        self.y = container.geometry.y
        self.width = container.geometry.width
        self.height = container.geometry.height


class Context:
    def __init__(self,
                 i3l: Connection,
                 tree: Con,
                 workspace_sequence: Optional[WorkspaceSequence]):
        self.i3l = i3l
        self.tree = tree
        self.focused = tree.find_focused()
        self.workspace = self.focused.workspace()
        self.containers = self._sync_containers(self.workspace)
        self.workspace_sequence = self._sync_workspace_sequence(self.containers, workspace_sequence) \
            if workspace_sequence is not None else None

    def contains_container(self, con_id: int) -> bool:
        containers = [container for container in self.containers if container.id == con_id]
        return len(containers) > 0

    def sorted_containers(self) -> List[Con]:
        return sorted(self.containers, key=lambda container: self.workspace_sequence.get_order(container.id))

    def workspace_width(self, ratio: float = 1.0) -> int:
        return int(self.workspace.rect.width * ratio)

    def workspace_height(self, ratio: float = 1.0) -> int:
        return int(self.workspace.rect.height * ratio)

    def exec(self, payload: str) -> List[CommandReply]:
        return self.i3l.command(payload)

    def send_tick(self, payload: str) -> TickReply:
        return self.i3l.send_tick(payload)

    def xdo_unmap_window(self, window_id: Optional[int] = None):
        if window_id is None:
            window_id = self.focused.window
        command = shlex.split(f'xdotool windowunmap {window_id}')
        subprocess.run(command)

    def xdo_map_window(self, rebuild_container: RebuildContainer):
        window_id = rebuild_container.window
        command = shlex.split(f'xdotool windowsize {window_id} {rebuild_container.width} {rebuild_container.height} '
                              f'windowmove {window_id} {rebuild_container.x} {rebuild_container.y} '
                              f'windowmap {window_id}')
        subprocess.run(command)

    def resync(self) -> 'Context':
        self.tree = self.i3l.get_tree()
        focused = self.tree.find_focused()
        workspace = focused.workspace()
        self.containers = self._sync_containers(workspace)
        return self

    @classmethod
    def _sync_containers(cls, workspace: Con) -> List[Con]:
        containers = [container for container in workspace if is_layout_container(container)]
        return sorted(containers, key=lambda container: container.window)

    @staticmethod
    def _sync_workspace_sequence(containers: List[Con], workspace_sequence: WorkspaceSequence) -> WorkspaceSequence:
        for container in containers:
            if workspace_sequence.get_order(container.id) is None:
                workspace_sequence.set_order(container)
        return workspace_sequence


class RebuildAction:

    def __init__(self):
        self.rebuild_cause: Optional[RebuildCause] = None
        self.containers_to_close: List[int] = []
        self.containers_to_recreate: List[RebuildContainer] = []
        self.container_id_to_focus: Optional[int] = None
        self.last_container_rebuilt: Optional[RebuildContainer] = None

    @staticmethod
    def _containers_after(con_id: int,
                          containers: List[Con],
                          workspace_sequence: WorkspaceSequence) -> List[RebuildContainer]:
        return [RebuildContainer(con) for con in containers
                if con_id == 0 or workspace_sequence.get_order(con.id) >= workspace_sequence.get_order(con_id)]

    def start_rebuild(self, context: Context, rebuild_cause: RebuildCause,
                      main_mark: str, last_mark: str, con_id: int = 0):
        if rebuild_cause is not None:
            self.rebuild_cause = rebuild_cause

        containers = context.sorted_containers()
        if len(containers) == 0 or (con_id != 0 and not context.workspace_sequence.contains(con_id)):
            self.end_rebuild(context)
            return

        self.containers_to_recreate = self._containers_after(con_id, containers, context.workspace_sequence)
        self.containers_to_close = []
        if len(self.containers_to_recreate) > 0:
            for rebuild_container in self.containers_to_recreate:
                context.xdo_unmap_window(rebuild_container.window)
                self.containers_to_close.append(rebuild_container.window)
            self.last_container_rebuilt = self.containers_to_recreate.pop(0)
            context.xdo_map_window(self.last_container_rebuilt)
        elif len(containers) == 1:
            context.exec(f'[con_id="{containers[-1].id}"] mark --add {main_mark}')
            context.exec(f'[con_id="{containers[-1].id}"] mark --add {last_mark}')
            self.end_rebuild(context)
        else:
            context.exec(f'[con_id="{containers[-1].id}"] mark --add {last_mark}')
            self.end_rebuild(context)

    def next_rebuild(self, context: Context):
        self.last_container_rebuilt = self.containers_to_recreate.pop(0)
        context.xdo_map_window(self.last_container_rebuilt)

    def end_rebuild(self, context: Context, cause: RebuildCause = None):
        rebuild_cause = self.rebuild_cause if cause is None else cause
        context.send_tick(f'i3-layouts rebuild {rebuild_cause.value}')
        if self.container_id_to_focus is not None:
            context.exec(f'[con_id="{self.container_id_to_focus}"] focus')
            self.container_id_to_focus = None
        if cause is None or self.rebuild_cause is None:
            self.rebuild_cause = None


class State:
    def __init__(self, i3):
        self.context: Optional[Context] = None
        self.workspace_sequences: Dict[str, WorkspaceSequence] = {}
        self.rebuild_action = RebuildAction()
        self.old_workspace_name = ''
        self.sync_context(i3)
        for workspace in i3.get_workspaces():
            if workspace.focused:
                self.add_workspace_sequence(workspace.name)
                self.prev_workspace_name = workspace.name

    def sync_context(self, i3l: Connection) -> Context:
        tree = i3l.get_tree()
        focused = tree.find_focused()
        workspace = focused.workspace()
        workspace_sequence = self.get_workspace_sequence(workspace.name)
        self.context = Context(i3l, tree, workspace_sequence)
        return self.context

    def handle_rebuild(self, context: Context, container: Con):
        if self.rebuild_action.rebuild_cause is None:
            self.end_rebuild(context, RebuildCause.WINDOW_NEW)
        elif len(self.rebuild_action.containers_to_recreate) == 0:
            self.end_rebuild(context)
        else:
            if self.rebuild_action.container_id_to_focus is None:
                self.rebuild_action.container_id_to_focus = container.id
            self.rebuild_action.next_rebuild(context)

    def start_rebuild(self, rebuild_cause: RebuildCause, context: Context,
                      main_mark: str, last_mark: str, con_id: int = 0):
        logger.debug(f'[state] rebuilding for {rebuild_cause}')
        self.rebuild_action.start_rebuild(context, rebuild_cause, main_mark, last_mark, con_id)

    def rebuild_closed_container(self, window_id: int) -> bool:
        if window_id in self.rebuild_action.containers_to_close:
            self.rebuild_action.containers_to_close.remove(window_id)
            return True
        return False

    def end_rebuild(self, context: Context, cause: RebuildCause = None):
        self.rebuild_action.end_rebuild(context, cause)

    def is_last_container_rebuilt(self, container: Con):
        return self.rebuild_action.last_container_rebuilt is not None and \
            self.rebuild_action.last_container_rebuilt.window == container.window

    def get_workspace_sequence(self, workspace_name: str) -> Optional[WorkspaceSequence]:
        return self.workspace_sequences[workspace_name] if workspace_name in self.workspace_sequences else None

    def add_workspace_sequence(self, workspace_name: str) -> WorkspaceSequence:
        if workspace_name not in self.workspace_sequences:
            workspace_sequence = WorkspaceSequence()
            self.workspace_sequences[workspace_name] = workspace_sequence
        if self.context.workspace.name == workspace_name:
            for container in self.context.containers:
                if not self.workspace_sequences[workspace_name].contains(container.id):
                    self.workspace_sequences[workspace_name].set_order(container)
                    self.workspace_sequences[workspace_name].set_stale(True)
        self.context.workspace_sequence = self.workspace_sequences[workspace_name]
        return self.workspace_sequences[workspace_name]
