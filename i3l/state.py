import logging
import shlex
import subprocess
from enum import Enum
from typing import Dict, List, Optional

from i3ipc import Con, Connection, CommandReply, TickReply

logger = logging.getLogger(__name__)


def is_layout_container(container: Con) -> bool:
    return container.window is not None and container.type == 'con' \
        and container.floating != 'auto_on' and container.floating != 'user_on'


class RebuildCause(Enum):
    LAYOUT_CHANGE_VSTACK = 'layout_change_vstack'
    LAYOUT_CHANGE_HSTACK = 'layout_change_hstack'
    LAYOUT_CHANGE_SPIRAL = 'layout_change_spiral'
    LAYOUT_CHANGE_COMPANION = 'layout_change_companion'
    LAYOUT_CHANGE_2COLUMNS = 'layout_change_2columns'
    LAYOUT_CHANGE_3COLUMNS = 'layout_change_3columns'
    LAYOUT_CHANGE_TABBED = 'layout_change_tabbed'
    WORKSPACE_FOCUS = 'workspace_focus'
    WINDOW_CLOSE = 'window_close'
    WINDOW_MOVE = 'window_move'
    WINDOW_NEW = 'window_new'

    @staticmethod
    def layout_change(layout_name: str) -> 'RebuildCause':
        return RebuildCause(f'layout_change_{layout_name}')


class WorkspaceSequence:
    def __init__(self):
        self.window_count = 0
        self.window_numbers: Dict[int, int] = {}
        self.is_stale = False
        self.stale_con_id = 0

    def set_order(self, container: Con):
        self.window_count += 1
        self.window_numbers[container.id] = self.window_count

    def get_order(self, con_id: int) -> Optional[int]:
        return self.window_numbers[con_id] if con_id in self.window_numbers else None

    def set_stale(self, stale: bool, con_id: int = 0):
        self.is_stale = stale
        if con_id == 0 or \
                self.stale_con_id == 0 or \
                self.window_numbers[con_id] < self.window_numbers[self.stale_con_id]:
            self.stale_con_id = con_id


class Context:
    def __init__(self,
                 i3l: Connection,
                 workspace: Con,
                 focused: Con,
                 workspace_sequence: Optional[WorkspaceSequence]):
        self.i3l = i3l
        self.workspace = workspace
        self.focused = focused
        self.containers = self._sync_containers(workspace)
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

    def xdo_map_window(self, window_id: Optional[int] = None):
        if window_id is None:
            window_id = self.focused.window
        command = shlex.split(f'xdotool windowmap {window_id}')
        subprocess.run(command)

    def resync(self) -> 'Context':
        tree = self.i3l.get_tree()
        focused = tree.find_focused()
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
        self.containers_to_recreate: List[int] = []

    @staticmethod
    def _containers_after(con_id: int, containers: List[Con], workspace_sequence: WorkspaceSequence):
        return [con.window for con in containers
                if con_id == 0 or workspace_sequence.get_order(con.id) >= workspace_sequence.get_order(con_id)]

    def start_rebuild(self, context: Context, rebuild_cause: RebuildCause,
                      main_mark: str, last_mark: str, con_id: int = 0):
        if rebuild_cause is not None:
            self.rebuild_cause = rebuild_cause

        containers = context.sorted_containers()
        if len(containers) == 0 or (con_id != 0 and con_id not in context.workspace_sequence.window_numbers):
            self.end_rebuild(context)
            return

        self.containers_to_recreate = self._containers_after(con_id, containers, context.workspace_sequence)
        self.containers_to_close = []
        if len(self.containers_to_recreate) > 0:
            for container_window_id in self.containers_to_recreate:
                context.xdo_unmap_window(container_window_id)
                self.containers_to_close.append(container_window_id)
            container_window_id = self.containers_to_recreate.pop(0)
            context.xdo_map_window(container_window_id)
        elif len(containers) == 1:
            context.exec(f'[con_id="{containers[-1].id}"] mark {main_mark}')
            self.end_rebuild(context)
        else:
            context.exec(f'[con_id="{containers[-1].id}"] mark {last_mark}')
            self.end_rebuild(context)

    def end_rebuild(self, context: Context, cause: RebuildCause = None):
        rebuild_cause = self.rebuild_cause if cause is None else cause
        context.send_tick(f'i3-layouts rebuild {rebuild_cause.value}')
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
        self.context = Context(i3l, workspace, focused, workspace_sequence)
        return self.context

    def has_rebuild_in_progress(self) -> bool:
        return self.rebuild_action.rebuild_cause is not None

    def is_rebuild_finished(self) -> bool:
        return self.has_rebuild_in_progress() and len(self.rebuild_action.containers_to_recreate) == 0

    def rebuild_closed_container(self, window_id: int) -> bool:
        return window_id in self.rebuild_action.containers_to_close

    def start_rebuild(self, rebuild_cause: RebuildCause, context: Context,
                      main_mark: str, last_mark: str, con_id: int = 0):
        logger.debug(f'[state] rebuilding for {rebuild_cause}')
        self.rebuild_action.start_rebuild(context, rebuild_cause, main_mark, last_mark, con_id)

    def recreate_next_window(self, context: Context):
        container_window_id = self.rebuild_action.containers_to_recreate.pop(0)
        context.xdo_map_window(container_window_id)

    def remove_closed_container(self, window_id: int):
        self.rebuild_action.containers_to_close.remove(window_id)

    def end_rebuild(self, context: Context, cause: RebuildCause = None):
        self.rebuild_action.end_rebuild(context, cause)

    def get_workspace_sequence(self, workspace_name: str) -> Optional[WorkspaceSequence]:
        return self.workspace_sequences[workspace_name] if workspace_name in self.workspace_sequences else None

    def add_workspace_sequence(self, workspace_name: str) -> WorkspaceSequence:
        if workspace_name not in self.workspace_sequences:
            workspace_sequence = WorkspaceSequence()
            self.workspace_sequences[workspace_name] = workspace_sequence
        if self.context.workspace.name == workspace_name:
            for container in self.context.containers:
                if container.id not in self.workspace_sequences[workspace_name].window_numbers:
                    self.workspace_sequences[workspace_name].set_order(container)
                    self.workspace_sequences[workspace_name].set_stale(True)
        self.context.workspace_sequence = self.workspace_sequences[workspace_name]
        return self.workspace_sequences[workspace_name]
