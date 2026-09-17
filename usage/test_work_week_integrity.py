"""Reset, receipt, and storage failure tests for the Work-only reference ledger."""
from dataclasses import replace
import sqlite3
import unittest
from unittest.mock import patch

from execution.test_support import make_spec
from usage import test_work_week as fixtures
from usage.work_week import WEEK_MS, WorkUsageError


class WorkWeekIntegrityTests(unittest.TestCase):
    setUp = fixtures.WorkWeekTests.setUp
    open = fixtures.WorkWeekTests.open
    reserve = fixtures.WorkWeekTests.reserve
    receipt = fixtures.WorkWeekTests.receipt

    def next_week(self):
        self.now = self.week.ends_ms
        self.ledger.configure_week(replace(self.week, period_id='week-2',
            starts_ms=self.now, ends_ms=self.now + WEEK_MS))

    def test_original_job_deadline_can_cross_week_without_shortening_or_renewal(self):
        deadline = self.week.ends_ms + 50000
        spec = make_spec('work:cosmo:light', deadline=deadline)
        before = spec.encoded
        result, _, quote = self.reserve(spec=spec)
        self.assertTrue(result['new_reservation'])
        self.next_week()
        repeated = self.ledger.reserve_for_job('work-1', spec, quote)
        self.assertFalse(repeated['new_reservation'])
        self.assertEqual(repeated['period_id'], 'week-1')
        self.assertEqual(self.ledger.snapshot()['previous_period_reserved_units'], 100)
        self.assertEqual(spec.encoded, before)
        self.assertEqual(spec.limits.deadline_unix_ms, deadline)

    def test_uncertain_previous_week_hold_stays_visible_and_restricts_capacity(self):
        self.reserve(units=1000)
        self.next_week()
        snapshot = self.ledger.snapshot()
        self.assertEqual(snapshot['remaining_percent'], 0)
        self.assertEqual(snapshot['previous_period_reserved_units'], 1000)
        with self.assertRaises(WorkUsageError):
            self.reserve('new-work', units=1)

    def test_settling_old_hold_releases_it_without_rebilling_old_usage_in_new_week(self):
        _, spec, _ = self.reserve(units=250)
        self.next_week()
        self.assertEqual(self.ledger.snapshot()['remaining_percent'], 75)
        self.receipt(spec, units=200)
        self.ledger.settle('work-1', 'receipt-1')
        snapshot = self.ledger.snapshot()
        self.assertEqual(snapshot['remaining_percent'], 100)
        self.assertEqual(snapshot['used_units'], 0)
        self.assertEqual(snapshot['previous_period_reserved_units'], 0)
        row = self.ledger.db.execute('SELECT period,settled FROM work_usage').fetchone()
        self.assertEqual(tuple(row), ('week-1', 200))

    def test_reservation_response_distinguishes_new_held_and_settled_without_dispatch_permission(self):
        first, spec, quote = self.reserve()
        self.assertTrue(first['new_reservation'])
        self.assertFalse(first['authorizes_dispatch'])
        repeated = self.ledger.reserve_for_job('work-1', spec, quote)
        self.assertFalse(repeated['new_reservation'])
        self.assertEqual(repeated['reservation_state'], 'held')
        self.receipt(spec)
        self.ledger.settle('work-1', 'receipt-1')
        settled = self.ledger.reserve_for_job('work-1', spec, quote)
        self.assertEqual(settled['reservation_state'], 'settled')
        self.assertFalse(settled['new_reservation'])
        self.assertFalse(settled['authorizes_dispatch'])

    def test_mismatched_persisted_receipt_and_settlement_cannot_create_spare_capacity(self):
        self.reserve()
        self.ledger.db.execute('UPDATE work_usage SET settled=0 WHERE job=?', ('work-1',))
        with self.assertRaisesRegex(WorkUsageError, '^work usage unavailable$'):
            self.ledger.snapshot()
        with self.assertRaises(WorkUsageError):
            self.reserve('next')

    def test_persisted_charge_exceeding_reserved_amount_is_rejected_on_repeated_reserve(self):
        _, spec, quote = self.reserve()
        self.ledger.db.execute('UPDATE work_usage SET settled=101,receipt=?', ('receipt',))
        with self.assertRaises(WorkUsageError):
            self.ledger.reserve_for_job('work-1', spec, quote)

    def test_quiescent_settlement_does_not_erase_mismatched_record_corruption(self):
        _, spec, _ = self.reserve()
        self.receipt(spec)
        self.ledger.db.execute('UPDATE work_usage SET reserved=1 WHERE job=?', ('work-1',))
        with self.assertRaises(WorkUsageError):
            self.ledger.settle('work-1', 'receipt-1')
        row = self.ledger.db.execute('SELECT receipt,settled FROM work_usage').fetchone()
        self.assertEqual(tuple(row), (None, None))

    def test_sql_storage_errors_are_sanitized_and_do_not_issue_admission(self):
        with patch.object(self.ledger, '_totals', side_effect=sqlite3.OperationalError('PRIVATE-PATH')):
            with self.assertRaisesRegex(WorkUsageError, '^work usage unavailable$'):
                self.reserve()
        self.assertEqual(self.ledger.db.execute('SELECT count(*) FROM work_usage').fetchone()[0], 0)

    def test_grant_change_on_last_clock_read_rolls_back_reservation(self):
        calls = 0
        original = self.g
        def clock():
            nonlocal calls
            calls += 1
            if calls == 3:
                self.g = replace(self.g, execution_authorized=False)
            return self.now
        second = self.open(clock_ms=clock)
        self.addCleanup(second.close)
        with self.assertRaises(WorkUsageError):
            self.reserve(ledger=second)
        self.g = original
        self.assertEqual(self.ledger.db.execute('SELECT count(*) FROM work_usage').fetchone()[0], 0)

    def test_active_previous_week_hold_stays_visible_after_database_reopen(self):
        self.reserve(units=125)
        self.next_week()
        second = self.open()
        self.addCleanup(second.close)
        snapshot = second.snapshot()
        self.assertEqual(snapshot['remaining_percent'], 87.5)
        self.assertEqual(snapshot['previous_period_reserved_units'], 125)
        self.assertEqual(snapshot['reserved_units'], 125)

    def test_chat_does_not_open_work_transaction_when_work_storage_is_unavailable(self):
        with patch.object(self.ledger, '_transaction', side_effect=sqlite3.OperationalError('offline')):
            result = self.ledger.reserve_for_job('chat', make_spec('instant'))
        self.assertFalse(result['metered'])
        self.assertEqual(result['work_units'], 0)
        self.assertFalse(result['authorizes_dispatch'])


if __name__ == '__main__':
    unittest.main()