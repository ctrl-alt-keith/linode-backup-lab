import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "linode_backup_lab"
PROVIDER_BOUNDARY = SRC_ROOT / "linode_api.py"


def source_files() -> list[Path]:
    return sorted(SRC_ROOT.glob("*.py"))


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_low_level_http_transport_stays_in_provider_boundary(self) -> None:
        offenders = []
        for path in source_files():
            if path == PROVIDER_BOUNDARY:
                continue
            text = path.read_text(encoding="utf-8")
            if "urllib.request" in text:
                offenders.append(path.relative_to(SRC_ROOT).as_posix())

        self.assertEqual(offenders, [])

    def test_provider_auth_header_literals_stay_in_provider_boundary(self) -> None:
        provider_auth_terms = ("Authorization", "Bearer")
        offenders: list[str] = []
        for path in source_files():
            if path == PROVIDER_BOUNDARY:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if any(term in node.value for term in provider_auth_terms):
                        offenders.append(path.relative_to(SRC_ROOT).as_posix())
                        break

        self.assertEqual(offenders, [])

