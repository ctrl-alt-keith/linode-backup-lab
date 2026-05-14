from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from linode_backup_lab.cli import main


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


class ManifestContractTests(unittest.TestCase):
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
    ) -> tuple[dict[str, object], str]:
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "backup-lab.toml"
            write_config(config_path)
            stdout = StringIO()
            stderr = StringIO()

            exit_code = main(
                [*command, "--config", str(config_path)],
                stdout=stdout,
                stderr=stderr,
                environ=environ,
                inspect_client_factory=inspect_client_factory,
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        emitted = stdout.getvalue()
        return json.loads(emitted), emitted

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


if __name__ == "__main__":
    unittest.main()
