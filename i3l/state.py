import shlex
import subprocess
from typing import Dict, List, Optional

from i3ipc import Con, Connection, CommandReply


class WorkspaceSequence:
    def __init__(self):
        self.window_count = 0
        self.window_numbers: Dict[int, int] = {}
        self.is_stale = False
        self.stale_con_id = 0

    def assign_number(self, container: Con):
        self.window_count += 1
        self.window_numbers[container.id] = self.window_count

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
                 containers: List[Con],
                 workspace_sequence: Optional[WorkspaceSequence]):
        self.i3l = i3l
        self.workspace = workspace
        self.focused = focused
        self.containers = containers
        self.workspace_sequence = workspace_sequence

    def contains_container(self, con_id: int) -> bool:
        containers = [container for container in self.containers if container.id == con_id]
        return len(containers) > 0

    def sorted_containers(self) -> List[Con]:
        return sorted(self.containers, key=lambda container: self.workspace_sequence.window_numbers[container.id])

    def workspace_width(self, ratio: float = 1.0) -> int:
        return int(self.workspace.rect.width * ratio)

    def workspace_height(self, ratio: float = 1.0) -> int:
        return int(self.workspace.rect.height * ratio)

    def exec(self, payload: str) -> List[CommandReply]:
        return self.i3l.command(payload)

    def xdo_unmap_window(self, window_id: Optional[int] = None):
        if window_id is None:
            window_id = self.focused.window
        command = shlex.split(f'xdotool windowunmap {window_id}')
        subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    def xdo_map_window(self, window_id: Optional[int] = None):
        if window_id is None:
            window_id = self.focused.window
        command = shlex.split(f'xdotool windowmap {window_id}')
        subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


class State:
    def __init__(self):
        self.context: Optional[Context] = None
        self.workspace_sequences: Dict[str, WorkspaceSequence] = {}
        self.containers_closed: List[int] = []
        self.containers_to_redraw: List[int] = []
        self.prev_workspace_name = ''
        self.old_workspace_name = ''

    def sync_context(self, i3l: Connection) -> Context:
        tree = i3l.get_tree()
        focused = tree.find_focused()
        workspace = focused.workspace()
        containers = [container for container in workspace if container.window is not None and container.type == 'con']
        containers = sorted(containers, key=lambda container: container.window)

        state = self.get_workspace_sequence(workspace.name)
        self.context = Context(i3l, workspace, focused, containers, state)
        return self.context

    def get_workspace_sequence(self, workspace_name: str) -> Optional[WorkspaceSequence]:
        return self.workspace_sequences[workspace_name] if workspace_name in self.workspace_sequences else None

    def add_workspace_sequence(self, workspace_name: str) -> WorkspaceSequence:
        if workspace_name not in self.workspace_sequences:
            state = WorkspaceSequence()
            self.workspace_sequences[workspace_name] = state
        if self.context.workspace.name == workspace_name:
            for container in self.context.containers:
                if container.id not in self.workspace_sequences[workspace_name].window_numbers:
                    self.workspace_sequences[workspace_name].assign_number(container)
                    self.workspace_sequences[workspace_name].set_stale(True)
        self.context.workspace_sequence = self.workspace_sequences[workspace_name]
        return self.workspace_sequences[workspace_name]
