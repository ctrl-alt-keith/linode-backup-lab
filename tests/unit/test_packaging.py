from pathlib import Path
import unittest

try:  # pragma: no cover - exercised only on Python 3.10
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised only on Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]


class PackagingTests(unittest.TestCase):
    def test_console_script_entry_point_uses_cli_main(self) -> None:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"

        with pyproject_path.open("rb") as pyproject_file:
            pyproject = tomllib.load(pyproject_file)

        project = pyproject["project"]
        self.assertEqual(project["license"], "Apache-2.0")
        self.assertEqual(project["license-files"], ["LICENSE"])
        self.assertEqual(project["scripts"]["linode-backup-lab"], "linode_backup_lab.cli:main")


if __name__ == "__main__":
    unittest.main()
