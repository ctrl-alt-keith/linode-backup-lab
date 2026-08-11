import unittest

from linode_backup_lab.review import (
    backup_state_visibility,
    mutation_review,
    provider_call_review,
    retry_recovery_review,
)


class ReviewTests(unittest.TestCase):
    def test_provider_call_review_ignores_malformed_items_and_sorts_summary(self) -> None:
        review = provider_call_review(
            {
                "occurred": True,
                "items": [
                    {"kind": "provider_read", "operation": "get_backup"},
                    {"kind": "provider_read", "operation": "list_backups"},
                    {"kind": "", "operation": None},
                    "not-a-record",
                ],
            }
        )

        self.assertEqual(
            review,
            {
                "occurred": True,
                "total": 3,
                "by_kind": {"provider_read": 2, "unknown": 1},
                "operations": ["get_backup", "list_backups", "unknown"],
            },
        )

    def test_mutation_review_keeps_explicit_safety_posture(self) -> None:
        review = mutation_review(
            {
                "planned_operation": "create_snapshot",
                "execution_requested": 1,
                "execution_allowed": False,
                "execution_performed": None,
            },
            provider_mutations="not_performed",
            skipped_reason="execution_not_available",
        )

        self.assertEqual(
            review,
            {
                "planned_operation": "create_snapshot",
                "execution_requested": True,
                "execution_allowed": False,
                "execution_performed": False,
                "provider_mutations": "not_performed",
                "skipped_reason": "execution_not_available",
            },
        )

    def test_backup_state_visibility_counts_unknown_snapshot_fields(self) -> None:
        review = backup_state_visibility(
            [
                {"backup_kind": "snapshot", "available": True, "snapshot_state": None},
                {"backup_kind": "automatic", "available": None, "config_count": None},
                {"backup_kind": None, "backup_status": None},
            ]
        )

        self.assertEqual(review["provider_backup_state"], "read")
        self.assertEqual(review["skipped_states"], ["provider_mutation"])
        self.assertEqual(
            review["unknown_fields"],
            {
                "available": 2,
                "backup_kind": 1,
                "backup_status": 3,
                "config_count": 3,
                "disk_count": 3,
                "provider_type": 3,
                "snapshot_state_for_snapshot": 1,
            },
        )

    def test_retry_recovery_review_covers_safe_uncertain_and_operator_states(self) -> None:
        cases = [
            (
                {"retry_classification": "safe_to_rerun_read_only"},
                {"status": "provider_local_match"},
                "safe_to_retry",
                "safe_to_retry",
            ),
            (
                {"operator_review_required": True},
                {"status": "provider_local_mismatch"},
                "operator_review_required",
                "operator_review_required",
            ),
            (
                {"state_uncertain": True},
                {"status": "provider_read_failed", "uncertain_state": True},
                "state_uncertain",
                "state_uncertain",
            ),
            (
                {},
                {"status": "fixture_replayed"},
                "operator_review_required",
                "refresh_before_retry",
            ),
        ]

        for outcome, state_assessment, command_retry, provider_state in cases:
            with self.subTest(outcome=outcome, state_assessment=state_assessment):
                review = retry_recovery_review(outcome, state_assessment)

                self.assertEqual(review["command_retry_classification"], command_retry)
                self.assertEqual(review["provider_state_classification"], provider_state)
                self.assertEqual(review["automatic_retry"], "not_performed")


if __name__ == "__main__":
    unittest.main()
