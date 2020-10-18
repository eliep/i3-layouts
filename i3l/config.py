import logging
import re
from typing import List, Optional

from i3ipc import ConfigReply

logger = logging.getLogger(__name__)


class Variable:
    def __init__(self, name: str, value: str):
        self.name = name
        self.value = value

    @staticmethod
    def extract_var(command) -> Optional['Variable']:
        match = re.match('set (\\$[^ ]*) ("?[^"]*"?)', command)
        if match:
            try:
                return Variable(match.group(1), match.group(2))
            except IndexError:
                return None
        return None


class WorkspaceLayout:
    def __init__(self, layout_name, layout_params, workspace_name):
        self.layout_name = layout_name
        self.layout_params = layout_params
        self.workspace_name = workspace_name

    @classmethod
    def load(cls, i3_config: ConfigReply) -> List['WorkspaceLayout']:
        i3_vars = {'$i3l': []}
        for command in i3_config.config.split('\n'):
            var = Variable.extract_var(command)
            if var is not None and var.name != '$i3l':
                i3_vars[var.name] = var.value
            elif var is not None:
                i3_vars[var.name].append(var.value)

        i3l_options = [' '.join([i3_vars[token] if token.startswith('$') else token for token in i3l_option.split(' ')])
                       for i3l_option in i3_vars['$i3l']]
        workspace_layouts = []
        for i3l_option in i3l_options:
            workspace_layout = cls._create_workspace_layout(i3l_option)
            if workspace_layout is not None:
                workspace_layouts.append(workspace_layout)
        return workspace_layouts

    @staticmethod
    def _create_workspace_layout(i3l_option) -> Optional['WorkspaceLayout']:
        match = re.match('([^ ]*) (.*) ?to workspace "?([^"]*)"?', i3l_option)
        if match:
            try:
                layout_name = match.group(1)
                layout_params = match.group(2).split(' ')
                workspace_name = match.group(3)
                return WorkspaceLayout(layout_name, layout_params, workspace_name)
            except IndexError:
                logger.error(f'[config] Invalid workspace layout definition: {i3l_option}')
                return None
        return None
