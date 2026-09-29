# Copyright (c) 2025, osama.ahmed@deliverydevs.com and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config import zkteco_config as zkteco


class TestZKTecoConfig(IntegrationTestCase):
	"""Tests for the ZKTeco Config single doctype and the device sync helpers.

	These deliberately avoid creating ERPNext Employees so they stay fast and independent of
	HR fixture data. HR-dependent behaviour is covered by `test_find_employee_by_code` falling
	back to a clean `None`.
	"""

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		frappe.db.set_single_value("ZKTeco Config", "enable_sync", 0)
		frappe.db.set_single_value("ZKTeco Config", "seconds", 300)
		frappe.db.set_single_value("ZKTeco Config", "server_ip", None)
		frappe.db.set_single_value("ZKTeco Config", "server_port", None)

		# Password fields live in __Auth, so they can only be cleared through the document.
		cfg = zkteco.get_config()
		if any(cfg.get(fieldname) for fieldname in ("token", "password")):
			cfg.set("token", None)
			cfg.set("password", None)
			cfg.save()

		frappe.cache().delete_value(zkteco.THROTTLE_KEY)

	def set_server(self, ip="10.0.0.1", port="80"):
		frappe.db.set_single_value("ZKTeco Config", "server_ip", ip)
		frappe.db.set_single_value("ZKTeco Config", "server_port", port)

	# --- URL building -----------------------------------------------------

	def test_build_url_adds_scheme_and_port(self):
		self.set_server("10.0.0.1", "8080")
		url = zkteco.build_url(zkteco.get_config(), "iclock/api/transactions/")

		self.assertEqual(url, "http://10.0.0.1:8080/iclock/api/transactions/")

	def test_build_url_keeps_existing_scheme(self):
		self.set_server("https://zk.example.com", "443")
		url = zkteco.build_url(zkteco.get_config(), "api-token-auth/")

		self.assertEqual(url, "https://zk.example.com:443/api-token-auth/")

	def test_build_url_does_not_duplicate_port(self):
		self.set_server("10.0.0.1:8080", "8080")
		url = zkteco.build_url(zkteco.get_config(), "iclock/api/transactions/")

		self.assertEqual(url, "http://10.0.0.1:8080/iclock/api/transactions/")

	def test_build_url_omits_blank_port(self):
		self.set_server("10.0.0.1", "")
		url = zkteco.build_url(zkteco.get_config(), "iclock/api/transactions/")

		self.assertEqual(url, "http://10.0.0.1/iclock/api/transactions/")

	def test_build_url_requires_server_ip(self):
		self.assertRaises(frappe.ValidationError, zkteco.build_url, zkteco.get_config(), "x")

	# --- Response parsing -------------------------------------------------

	def test_parse_transaction_response_handles_data_key(self):
		transactions, count, next_url = zkteco.parse_transaction_response(
			{"count": 12, "data": [{"id": 1}, {"id": 2}], "next": "http://x?page=2"}
		)

		self.assertEqual(len(transactions), 2)
		self.assertEqual(count, 12)
		self.assertEqual(next_url, "http://x?page=2")

	def test_parse_transaction_response_handles_results_key(self):
		transactions, count, next_url = zkteco.parse_transaction_response(
			{"results": [{"id": 1}]}
		)

		self.assertEqual(len(transactions), 1)
		self.assertEqual(count, 1)
		self.assertIsNone(next_url)

	def test_parse_transaction_response_handles_bare_list(self):
		transactions, count, next_url = zkteco.parse_transaction_response([{"id": 1}])

		self.assertEqual(count, 1)
		self.assertIsNone(next_url)

	def test_parse_transaction_response_handles_garbage(self):
		self.assertEqual(zkteco.parse_transaction_response("nonsense"), ([], 0, None))
		self.assertEqual(zkteco.parse_transaction_response(None), ([], 0, None))
		self.assertEqual(zkteco.parse_transaction_response({}), ([], 0, None))

	# --- Punch mapping ----------------------------------------------------

	def test_map_log_type(self):
		self.assertEqual(zkteco.map_log_type("1"), "OUT")
		self.assertEqual(zkteco.map_log_type(1), "OUT")
		self.assertEqual(zkteco.map_log_type("0"), "IN")
		self.assertEqual(zkteco.map_log_type(None, "Check Out"), "OUT")
		self.assertEqual(zkteco.map_log_type("0", "Check In"), "IN")
		self.assertEqual(zkteco.map_log_type(None, "Check In-Out"), "IN")

	def test_get_device_id_is_stable_and_unique_per_transaction(self):
		first = zkteco.get_device_id({"id": 7, "terminal_alias": "Main Gate"})
		second = zkteco.get_device_id({"id": 8, "terminal_alias": "Main Gate"})

		self.assertEqual(first, "Main Gate (ZKTeco-7)")
		self.assertNotEqual(first, second)
		self.assertEqual(first, zkteco.get_device_id({"id": 7, "terminal_alias": "Main Gate"}))

	def test_get_device_id_falls_back_to_serial_number(self):
		self.assertEqual(zkteco.get_device_id({"terminal_sn": "SN123"}), "SN123")
		self.assertEqual(zkteco.get_device_id({}), "ZKTeco Device")

	def test_get_device_id_is_truncated(self):
		device_id = zkteco.get_device_id({"id": 1, "terminal_alias": "x" * 300})

		self.assertLessEqual(len(device_id), zkteco.DEVICE_ID_MAX_LENGTH)

	# --- Employee mapping -------------------------------------------------

	def test_find_employee_by_code_returns_none_for_unknown_code(self):
		self.assertIsNone(zkteco.find_employee_by_code("__no_such_employee__"))
		self.assertIsNone(zkteco.find_employee_by_code(None))
		self.assertIsNone(zkteco.find_employee_by_code(""))

	# --- Sync behaviour ---------------------------------------------------

	def test_sync_is_skipped_when_disabled(self):
		result = zkteco.sync_zkteco_transactions()

		self.assertTrue(result["skipped"])
		self.assertEqual(result["processed"], 0)

	def test_sync_is_skipped_without_token(self):
		self.set_server()
		frappe.db.set_single_value("ZKTeco Config", "enable_sync", 1)

		result = zkteco.sync_zkteco_transactions()

		self.assertTrue(result["skipped"])

	def test_scheduled_sync_does_nothing_when_disabled(self):
		# Must not raise, and must not touch the device.
		zkteco.scheduled_sync()

	def test_scheduled_sync_throttles_repeated_runs(self):
		"""A second tick inside the configured interval must not hit the device again."""
		self.set_server()
		frappe.db.set_single_value("ZKTeco Config", "enable_sync", 1)
		frappe.db.set_single_value("ZKTeco Config", "seconds", 3600)

		cfg = zkteco.get_config()
		cfg.token = "test-token"
		cfg.save()

		calls = []
		original = zkteco.request_transactions

		def counting_request(cfg, token, params):
			calls.append(1)
			return [], 0

		zkteco.request_transactions = counting_request
		try:
			zkteco.scheduled_sync()
			first_run = len(calls)
			zkteco.scheduled_sync()
			zkteco.scheduled_sync()
			second_run = len(calls)
		finally:
			zkteco.request_transactions = original

		self.assertEqual(first_run, 1)
		self.assertEqual(second_run, 1)

	def test_get_sync_window_defaults_to_last_hour(self):
		start_time, end_time = zkteco.get_sync_window(zkteco.get_config())

		self.assertLess(start_time, end_time)
		self.assertGreater((end_time - start_time).total_seconds(), 3500)

	def test_get_sync_window_ignores_future_last_sync(self):
		frappe.db.set_single_value("ZKTeco Config", "last_sync", "2999-01-01 00:00:00")

		start_time, end_time = zkteco.get_sync_window(zkteco.get_config())

		self.assertLess(start_time, end_time)

	def test_create_employee_checkin_rejects_incomplete_transaction(self):
		self.assertFalse(zkteco.create_employee_checkin({"punch_time": "2025-01-01 08:00:00"}))
		self.assertFalse(zkteco.create_employee_checkin({"emp_code": "0001"}))

	def test_create_employee_checkin_skips_unmapped_employee(self):
		created = zkteco.create_employee_checkin(
			{"emp_code": "__no_such_employee__", "punch_time": "2025-01-01 08:00:00", "id": 1}
		)

		self.assertFalse(created)

	def test_get_token_is_none_when_not_configured(self):
		self.assertIsNone(zkteco.get_token(zkteco.get_config()))
