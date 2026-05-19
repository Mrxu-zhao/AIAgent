import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()

from collaboration.kanban import KanbanBoard, TaskStatus
from collaboration.skill_curator import SkillCurator


class CollaborationTests(unittest.TestCase):
    def test_kanban_board_summary_counts_in_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = KanbanBoard(str(Path(tmp) / "kanban.db"))
            task = board.create_task("Integrate module")
            board.move_task(task.id, TaskStatus.IN_PROGRESS, actor="architect")
            self.assertEqual(board.get_board_summary()["in_progress"], 1)

    def test_skill_curator_register_and_use(self):
        curator = SkillCurator(storage_backend="memory")
        curator.register_skill("demo", "desc", "return True")
        used = curator.use_skill("demo")
        self.assertEqual(used["name"], "demo")


if __name__ == "__main__":
    unittest.main()
