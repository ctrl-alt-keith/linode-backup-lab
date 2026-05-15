from io import StringIO
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest

from linode_backup_lab.cli import main
from linode_backup_lab.config import BackupLabConfig, TargetConfig
from linode_backup_lab.inspect import create_inspect_failure_manifest, create_inspect_manifest
from linode_backup_lab.linode_api import ProviderError
from linode_backup_lab.plan import create_plan_manifest
from linode_backup_lab.replay import create_replay_inspect_manifest
from linode_backup_lab.snapshot import snapshot_manifest


REPO_ROOT = Path(__file__).resolve().parents[2]


BASE_TOP_LEVEL_FIELDS = {
    "schema_version",
    "provider",
    "run_id",
    "created_at",
    "action",
    "dry_run",
    "status",
    "resources",
}

PLAN_CONTRACT_FIELDS = BASE_TOP_LEVEL_FIELDS | {
    "command",
    "config",
    "planned_actions",
    "review",
    "mutation_intent",
    "state_assessment",
    "outcome",
    "validation",
    "safety",
}

INSPECT_CONTRACT_FIELDS = BASE_TOP_LEVEL_FIELDS | {
    "command",
    "config",
    "provider_read",
    "provider_documented_fields",
    "inspection_summary",
    "normalized_backup_state",
    "review",
    "mutation_intent",
    "state_assessment",
    "outcome",
    "validation",
    "safety",
}

REVIEW_PACKET_FIELDS = {
    "provider_calls",
    "mutations",
    "state_visibility",
    "retry_recovery",
}

SHARED_COMMAND_FIELDS = {
    "name",
    "config_source",
    "config_path_recorded",
    "provider_calls",
}


def write_config(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                'schema_version = "1"',
                "",
                "[target]",
                "linode_id = 445566",
                'snapshot_label = "private-contract-label"',
            ]
        ),
        encoding="utf-8",
    )


class ContractInspectClient:
    provider_api_version = "v4"

    def __init__(self, token: str) -> None:
        self.token = token

    def list_backups(self, linode_id: int) -> list[dict[str, object]]:
        return [
            {
                "backup_id": 998877,
                "backup_label": "private-contract-label",
                "backup_status": "successful",
                "backup_kind": "snapshot",
                "snapshot_state": "current",
                "provider_type": "snapshot",
                "available": True,
                "created_at": "2026-05-07T12:00:00",
                "finished_at": "2026-05-07T12:05:00",
                "updated_at": "2026-05-07T12:06:00",
                "config_count": 1,
                "disk_count": 2,
            },
            {
                "backup_id": 887766,
                "backup_label": None,
                "backup_status": "successful",
                "backup_kind": "automatic",
                "snapshot_state": None,
                "provider_type": "auto",
                "available": True,
                "created_at": "2026-05-07T00:00:00",
                "finished_at": "2026-05-07T00:05:00",
                "updated_at": "2026-05-07T00:06:00",
                "config_count": 1,
                "disk_count": 2,
            },
        ]


class ContractFailingInspectClient:
    provider_api_version = "v4"

    def __init__(self, token: str) -> None:
        self.token = token

    def list_backups(self, linode_id: int) -> list[dict[str, object]]:
        raise ProviderError(
            f"raw provider detail token={self.token} linode={linode_id}",
            public_message="Linode API returned invalid JSON",
            category="invalid_json",
            request_sent=True,
            response_received=True,
        )


class StaticInspectClient:
    provider_api_version = "v4"

    def __init__(self, backups: list[dict[str, object]]) -> None:
        self.backups = backups

    def list_backups(self, linode_id: int) -> list[dict[str, object]]:
        return self.backups


class ManifestContractTests(unittest.TestCase):
    def test_emitted_manifests_share_command_required_subset(self) -> None:
        manifests = [
            self.emit_manifest(["plan"])[0],
            self.emit_manifest(
                ["inspect"],
                environ={"LINODE_TOKEN": "contract-token-secret"},
                inspect_client_factory=ContractInspectClient,
            )[0],
            self.emit_manifest(
                ["inspect"],
                environ={"LINODE_TOKEN": "contract-token-secret"},
                inspect_client_factory=ContractFailingInspectClient,
                expected_exit_code=1,
                expected_stderr="Linode API returned invalid JSON",
            )[0],
            self.emit_manifest(["inspect-replay"], use_fixture=True)[0],
        ]

        for manifest in manifests:
            with self.subTest(action=manifest["action"], status=manifest["status"]):
                self.assertLessEqual(SHARED_COMMAND_FIELDS, set(manifest["command"]))
                self.assertIsInstance(manifest["command"]["name"], str)
                self.assertEqual(manifest["command"]["config_source"], "explicit")
                self.assertIs(manifest["command"]["config_path_recorded"], False)
                self.assert_provider_calls_shape(manifest["command"]["provider_calls"])

    def test_validation_status_vocabulary_documents_current_emitted_values(self) -> None:
        config = BackupLabConfig(
            schema_version="1",
            target=TargetConfig(linode_id=445566, snapshot_label="private-contract-label"),
        )
        emitted_statuses = {
            create_plan_manifest(config)["validation"]["status"],
            snapshot_manifest(config=config)["validation"]["status"],
            create_inspect_manifest(
                config,
                client=StaticInspectClient(
                    [
                        {
                            "backup_label": "private-contract-label",
                            "backup_kind": "snapshot",
                            "snapshot_state": "current",
                        }
                    ]
                ),
            )["validation"]["status"],
            create_inspect_manifest(
                config,
                client=StaticInspectClient(
                    [
                        {
                            "backup_label": "other-private-label",
                            "backup_kind": "snapshot",
                            "snapshot_state": "current",
                        }
                    ]
                ),
            )["validation"]["status"],
            create_inspect_manifest(
                config,
                client=StaticInspectClient(
                    [
                        {
                            "backup_label": "private-contract-label",
                            "backup_kind": "snapshot",
                            "snapshot_state": "in_progress",
                        }
                    ]
                ),
            )["validation"]["status"],
            create_inspect_failure_manifest(
                config,
                provider_error=ProviderError("private provider detail", request_sent=True),
            )["validation"]["status"],
            create_replay_inspect_manifest(
                config,
                fixture_backups=[
                    {
                        "backup_label": "SANITIZED_CONTRACT_LABEL",
                        "backup_kind": "snapshot",
                        "snapshot_state": "current",
                    }
                ],
            )["validation"]["status"],
        }

        self.assertEqual(emitted_statuses, self.documented_validation_statuses())

    def test_schema_artifact_groundwork_inventories_current_top_level_fields(self) -> None:
        config = BackupLabConfig(
            schema_version="1",
            target=TargetConfig(linode_id=445566, snapshot_label="private-contract-label"),
        )
        manifests = [
            create_plan_manifest(config),
            snapshot_manifest(config=config),
            create_inspect_manifest(config, client=ContractInspectClient("contract-token-secret")),
            create_inspect_failure_manifest(
                config,
                provider_error=ProviderError("private provider detail", request_sent=True),
            ),
            create_replay_inspect_manifest(
                config,
                fixture_backups=[
                    {
                        "backup_id": "SANITIZED_BACKUP_ID",
                        "backup_label": "SANITIZED_CONTRACT_LABEL",
                        "backup_status": "successful",
                        "backup_kind": "snapshot",
                        "snapshot_state": "current",
                        "provider_type": "snapshot",
                        "available": True,
                        "created_at": "SANITIZED_PROVIDER_TIMESTAMP",
                        "finished_at": "SANITIZED_PROVIDER_TIMESTAMP",
                        "updated_at": "SANITIZED_PROVIDER_TIMESTAMP",
                        "config_count": 1,
                        "disk_count": 1,
                    }
                ],
            ),
        ]
        emitted_top_level_fields = sorted({field for manifest in manifests for field in manifest})
        groundwork = (REPO_ROOT / "docs" / "schema-artifact-groundwork.md").read_text(encoding="utf-8")

        for field in emitted_top_level_fields:
            with self.subTest(field=field):
                self.assertIn(f"`{field}`", groundwork)
        self.assertIn("not a generated schema", groundwork)
        self.assertIn("not a new validation gate", groundwork)

    def test_plan_emitted_json_contract_keeps_dry_run_shape_and_redaction(self) -> None:
        manifest, emitted = self.emit_manifest(["plan"])

        self.assertLessEqual(PLAN_CONTRACT_FIELDS, set(manifest))
        self.assertEqual(manifest["action"], "plan")
        self.assertIs(manifest["dry_run"], True)
        self.assertEqual(manifest["status"], "planned")
        self.assertEqual(manifest["provider"], {"name": "linode", "api_version": "v4"})
        self.assertEqual(manifest["config"], {"schema_version": "1"})
        self.assertEqual(set(manifest["review"]), REVIEW_PACKET_FIELDS)

        self.assertEqual(manifest["command"]["name"], "plan")
        self.assertEqual(manifest["command"]["config_source"], "explicit")
        self.assertIs(manifest["command"]["config_path_recorded"], False)
        self.assertEqual(manifest["command"]["provider_calls"], {"occurred": False, "items": []})
        self.assertEqual(
            manifest["review"]["provider_calls"],
            {"occurred": False, "total": 0, "by_kind": {}, "operations": []},
        )

        planned_action = manifest["planned_actions"][0]
        self.assertEqual(planned_action["effect"], "dry_run_only")
        self.assertIs(planned_action["provider_read"], False)
        self.assertIs(planned_action["provider_mutation"], False)
        self.assertEqual(manifest["safety"]["provider_reads"], "not_performed")
        self.assertEqual(manifest["safety"]["provider_mutations"], "not_performed")
        self.assertIs(manifest["safety"]["linode_token_required"], False)

        self.assertEqual(manifest["mutation_intent"]["planned_operation"], "snapshot_request")
        self.assertIs(manifest["mutation_intent"]["execution_requested"], False)
        self.assertIs(manifest["mutation_intent"]["execution_allowed"], False)
        self.assertIs(manifest["mutation_intent"]["execution_performed"], False)
        self.assertEqual(manifest["state_assessment"]["status"], "unverified_provider_state")
        self.assertIs(manifest["state_assessment"]["refresh_before_mutation"]["required"], True)
        self.assertEqual(manifest["outcome"]["execution_state"], "not_started")
        self.assertEqual(manifest["outcome"]["retry_classification"], "safe_to_rerun_no_provider_request")
        self.assertEqual(manifest["outcome"]["idempotency_boundary"], "no_provider_request_sent")
        self.assertEqual(manifest["outcome"]["provider_reads"], [])
        self.assertEqual(manifest["outcome"]["provider_mutations"], [])
        self.assertEqual(manifest["review"]["retry_recovery"]["command_retry_classification"], "safe_to_retry")
        self.assertEqual(
            manifest["review"]["retry_recovery"]["provider_state_classification"],
            "refresh_before_retry",
        )

        self.assert_redacted_target(manifest["resources"][0]["target"])
        self.assert_redacted_target(planned_action["target"])
        self.assertNotIn("445566", emitted)
        self.assertNotIn("private-contract-label", emitted)

    def test_inspect_emitted_json_contract_reports_read_only_provider_call_and_redaction(self) -> None:
        manifest, emitted = self.emit_manifest(
            ["inspect"],
            environ={"LINODE_TOKEN": "contract-token-secret"},
            inspect_client_factory=ContractInspectClient,
        )

        self.assertLessEqual(INSPECT_CONTRACT_FIELDS, set(manifest))
        self.assertEqual(manifest["action"], "inspect")
        self.assertIs(manifest["dry_run"], False)
        self.assertEqual(manifest["status"], "inspected")
        self.assertEqual(manifest["provider"], {"name": "linode", "api_version": "v4"})
        self.assertEqual(manifest["config"], {"schema_version": "1"})
        self.assertEqual(set(manifest["review"]), REVIEW_PACKET_FIELDS)

        provider_call = {"kind": "read", "method": "GET", "operation": "list_backups"}
        self.assertEqual(manifest["command"]["name"], "inspect")
        self.assertEqual(manifest["command"]["config_source"], "explicit")
        self.assertIs(manifest["command"]["config_path_recorded"], False)
        self.assertEqual(manifest["command"]["token_source"], "environment")
        self.assertEqual(manifest["command"]["provider_calls"], {"occurred": True, "items": [provider_call]})
        self.assertEqual(
            manifest["review"]["provider_calls"],
            {"occurred": True, "total": 1, "by_kind": {"read": 1}, "operations": ["list_backups"]},
        )
        self.assertEqual(
            manifest["provider_read"],
            {
                "status": "performed",
                "operation": "list_backups",
                "method": "GET",
                "target": "configured_linode_backups",
                "raw_response_recorded": False,
            },
        )

        self.assertEqual(manifest["safety"]["provider_reads"], "performed")
        self.assertEqual(manifest["safety"]["provider_mutations"], "not_performed")
        self.assertIs(manifest["safety"]["linode_token_required"], True)
        self.assertIs(manifest["safety"]["linode_token_recorded"], False)
        self.assertIs(manifest["safety"]["read_only_enforced"], True)
        self.assertIs(manifest["safety"]["raw_provider_response_recorded"], False)
        self.assertEqual(manifest["safety"]["target_values"], "redacted")
        self.assertEqual(manifest["safety"]["backup_identifiers"], "redacted")

        self.assertIsNone(manifest["mutation_intent"]["planned_operation"])
        self.assertIs(manifest["mutation_intent"]["execution_requested"], False)
        self.assertIs(manifest["mutation_intent"]["execution_allowed"], False)
        self.assertIs(manifest["mutation_intent"]["execution_performed"], False)
        self.assertEqual(manifest["state_assessment"]["source"], "fresh_provider_read")
        self.assertIs(manifest["state_assessment"]["provider_read_performed"], True)
        self.assertIs(manifest["state_assessment"]["refresh_before_mutation"]["required"], True)
        self.assertEqual(manifest["outcome"]["execution_state"], "completed")
        self.assertEqual(manifest["outcome"]["retry_classification"], "safe_to_rerun_read_only")
        self.assertEqual(manifest["outcome"]["idempotency_boundary"], "read_only_provider_request")
        self.assertEqual(
            manifest["outcome"]["provider_reads"],
            [{**provider_call, "request_sent": True, "response_received": True}],
        )
        self.assertEqual(manifest["outcome"]["provider_mutations"], [])
        self.assertEqual(manifest["review"]["retry_recovery"]["command_retry_classification"], "safe_to_retry")

        self.assert_redacted_target(manifest["resources"][0]["target"])
        self.assert_redacted_target(manifest["inspection_summary"]["target"])
        first_backup = manifest["normalized_backup_state"][0]
        self.assertTrue(first_backup["backup_id"]["redacted"])
        self.assertTrue(first_backup["backup_label"]["redacted"])
        self.assertTrue(first_backup["created_at"]["redacted"])
        self.assertNotIn("contract-token-secret", emitted)
        self.assertNotIn("445566", emitted)
        self.assertNotIn("998877", emitted)
        self.assertNotIn("887766", emitted)
        self.assertNotIn("private-contract-label", emitted)
        self.assertNotIn("2026-05-07T12:00:00", emitted)

    def emit_manifest(
        self,
        command: list[str],
        *,
        environ: dict[str, str] | None = None,
        inspect_client_factory: object | None = None,
        expected_exit_code: int = 0,
        expected_stderr: str = "",
        use_fixture: bool = False,
    ) -> tuple[dict[str, object], str]:
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "backup-lab.toml"
            write_config(config_path)
            fixture_args = []
            if use_fixture:
                fixture_path = Path(tmpdir) / "inspect-fixture.json"
                write_replay_fixture(fixture_path)
                fixture_args = ["--fixture", str(fixture_path)]
            stdout = StringIO()
            stderr = StringIO()

            exit_code = main(
                [*command, "--config", str(config_path), *fixture_args],
                stdout=stdout,
                stderr=stderr,
                environ=environ,
                inspect_client_factory=inspect_client_factory,
            )

        self.assertEqual(exit_code, expected_exit_code)
        if expected_stderr:
            self.assertIn(expected_stderr, stderr.getvalue())
        else:
            self.assertEqual(stderr.getvalue(), "")
        emitted = stdout.getvalue()
        return json.loads(emitted), emitted

    def assert_provider_calls_shape(self, provider_calls: object) -> None:
        self.assertIsInstance(provider_calls, dict)
        self.assertEqual(set(provider_calls), {"occurred", "items"})
        self.assertIsInstance(provider_calls["occurred"], bool)
        self.assertIsInstance(provider_calls["items"], list)
        for item in provider_calls["items"]:
            self.assertLessEqual({"kind", "method", "operation"}, set(item))

    def documented_validation_statuses(self) -> set[str]:
        docs = (REPO_ROOT / "docs" / "manifest-cli-contract.md").read_text(encoding="utf-8")
        section = re.search(
            r"^## Validation Status Vocabulary\n(?P<body>.*?)(?=^## |\Z)",
            docs,
            flags=re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(section)
        return set(re.findall(r"^\| `([^`]+)` \|", section.group("body"), flags=re.MULTILINE))

    def assert_redacted_target(self, target: dict[str, object]) -> None:
        self.assertEqual(
            target,
            {
                "linode_id": {
                    "present": True,
                    "redacted": True,
                    "validated_as": "positive_integer",
                },
                "snapshot_label": {
                    "present": True,
                    "redacted": True,
                    "validated_as": "linode_snapshot_label_length_1_255",
                },
            },
        )


def write_replay_fixture(path: Path) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "backup_id": "SANITIZED_BACKUP_ID",
                    "backup_label": "SANITIZED_SNAPSHOT_LABEL",
                    "backup_status": "successful",
                    "backup_kind": "snapshot",
                    "snapshot_state": "current",
                    "provider_type": "snapshot",
                    "available": True,
                    "created_at": "SANITIZED_PROVIDER_TIMESTAMP",
                    "finished_at": "SANITIZED_PROVIDER_TIMESTAMP",
                    "updated_at": "SANITIZED_PROVIDER_TIMESTAMP",
                    "config_count": 1,
                    "disk_count": 1,
                }
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
