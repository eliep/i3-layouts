import logging
import sys
import unittest

from i3ipc import Connection
from i3l.config import WorkspaceLayout

logging.basicConfig(stream=sys.stdout,
                    format='[%(asctime)s] %(levelname)s {%(filename)s:%(lineno)d} - %(message)s',
                    level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TestI3ConfigParsing:

    def test_extra_spaces_in_variables_declaration(self):
        i3 = Connection()

        i3_config = i3.get_config()
        workspace_layouts = WorkspaceLayout.load(i3_config)
        layouts = {wl.workspace_name: {'name': wl.layout_name, 'params': wl.layout_params} for wl in workspace_layouts}
        assert len(layouts) == 3
        assert layouts["8"]['name'] == "spiral"
        assert len(layouts["8"]['params']) == 2
        assert layouts["8"]['params'][0] == "0.6"
        assert layouts["8"]['params'][1] == "outside"
        assert layouts["9"]['name'] == "vstack"
        assert len(layouts["9"]['params']) == 1
        assert layouts["9"]['params'][0] == "0.3"
        assert layouts["10"]['name'] == "hstack"
        assert len(layouts["10"]['params']) == 0


if __name__ == '__main__':
    unittest.main()
