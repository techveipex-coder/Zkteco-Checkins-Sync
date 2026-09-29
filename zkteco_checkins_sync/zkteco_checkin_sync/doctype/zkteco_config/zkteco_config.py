# Copyright (c) 2025, osama.ahmed@deliverydevs.com
# For license information, please see license.txt

import json
from datetime import timedelta

import frappe
import requests
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, get_datetime, now_datetime, today

ZKTECO_CONFIG = "ZKTeco Config"
ALLOWED_ROLES = ("System Manager", "HR Manager", "HR User")

REQUEST_TIMEOUT = 30
MAX_PAGES = 20
DEFAULT_SYNC_SECONDS = 300
MIN_SYNC_SECONDS = 10
THROTTLE_KEY = "zkteco_checkins_sync:next_run_at"
DEVICE_ID_MAX_LENGTH = 140


class ZKTecoConfig(Document):
	pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_config() -> Document:
	"""Return the `ZKTeco Config` single doctype."""
	return frappe.get_single(ZKTECO_CONFIG)


def get_token(cfg: Document) -> str | None:
	"""Return the decrypted API token.

	`token` is a Password field, so the value stored on the document is only a masked
	placeholder. Reading it via `frappe.db.get_single_value` would return the encrypted blob
	and never authenticate, so always go through `get_password`.
	"""
	return (cfg.get_password("token", raise_exception=False) or "").strip() or None


def build_url(cfg: Document, path: str) -> str:
	"""Build an absolute URL for the ZKBio Time server.

	Accepts a bare IP (`10.0.0.1`, `10.0.0.1:8080`) as well as a host that already carries a
	scheme, and does not duplicate the port if it is already part of the host.
	"""
	host = (cfg.server_ip or "").strip().rstrip("/")
	if not host:
		frappe.throw(_("Please configure the server IP in {0}.").format(ZKTECO_CONFIG))

	if "://" not in host:
		host = f"http://{host}"

	scheme, remainder = host.split("://", 1)

	port = cint(cfg.server_port)
	if port and ":" not in remainder.rsplit("/", 1)[-1]:
		remainder = f"{remainder}:{port}"

	return f"{scheme}://{remainder.rstrip('/')}/{path.lstrip('/')}"


def get_headers(token: str) -> dict:
	return {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}


def parse_transaction_response(payload) -> tuple[list, int, str | None]:
	"""Normalize the different response shapes returned by ZKBio Time / iClock.

	Returns `(transactions, total_count, next_page_url)`.
	"""
	if isinstance(payload, dict):
		if isinstance(payload.get("data"), list):
			transactions = payload["data"]
		elif isinstance(payload.get("results"), list):
			transactions = payload["results"]
		else:
			transactions = []

		return transactions, cint(payload.get("count")) or len(transactions), payload.get("next")

	if isinstance(payload, list):
		return payload, len(payload), None

	return [], 0, None


def map_log_type(punch_state, punch_state_display: str | None = None) -> str:
	"""Map a device punch state onto an ERPNext `log_type`."""
	if cint(punch_state) == 1:
		return "OUT"

	if (punch_state_display or "").strip().lower() == "check out":
		return "OUT"

	return "IN"


def get_device_id(transaction: dict) -> str:
	"""Return a stable, unique device id for a transaction.

	The transaction id is embedded so the same punch is always mapped to the same
	`Employee Checkin.device_id`, which is what makes de-duplication work.
	"""
	device = transaction.get("terminal_alias") or transaction.get("terminal_sn") or "ZKTeco Device"
	transaction_id = transaction.get("id")

	device_id = f"{device} (ZKTeco-{transaction_id})" if transaction_id else str(device)
	return device_id[:DEVICE_ID_MAX_LENGTH]


def find_employee_by_code(emp_code: str) -> str | None:
	"""Find an Employee by any of the identifiers a device can report."""
	if not emp_code:
		return None

	emp_code = str(emp_code).strip()

	for fieldname in ("employee", "user_id", "attendance_device_id"):
		# `attendance_device_id` only exists on ERPNext >= v14; check the meta instead of the
		# database so this keeps working across versions.
		if not frappe.get_meta("Employee").has_field(fieldname):
			continue

		name = frappe.db.get_value("Employee", {fieldname: emp_code}, "name")
		if name:
			return name

	return None


def get_sync_window(cfg: Document) -> tuple:
	"""Return the `(start_time, end_time)` window to pull from the device."""
	end_time = now_datetime()
	last_sync = cfg.last_sync

	if isinstance(last_sync, str):
		last_sync = get_datetime(last_sync) if last_sync else None

	# Fall back to the last hour when there is no previous run, or when the stored timestamp
	# is in the future (clock skew / manual edit).
	if not last_sync or last_sync > end_time:
		last_sync = end_time - timedelta(hours=1)

	return last_sync, end_time


# ---------------------------------------------------------------------------
# Device API
# ---------------------------------------------------------------------------


def request_transactions(cfg: Document, token: str, params: dict) -> tuple[list, int]:
	"""Fetch transactions from the device, following pagination when the API provides it."""
	url = build_url(cfg, "iclock/api/transactions/")
	headers = get_headers(token)

	transactions: list = []
	total = 0
	query = dict(params)

	for page in range(1, MAX_PAGES + 1):
		response = requests.get(url, headers=headers, params=query, timeout=REQUEST_TIMEOUT)
		response.raise_for_status()

		batch, count, next_url = parse_transaction_response(response.json())
		transactions.extend(batch)
		total = max(total, count)

		if not next_url or not batch:
			break

		query = dict(params, page=page + 1)

	return transactions, total


# ---------------------------------------------------------------------------
# Whitelisted methods
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
def register_api_token():
	"""Exchange the ZKTeco superuser credentials for an API token and store it."""
	frappe.only_for(ALLOWED_ROLES)

	cfg = get_config()
	password = cfg.get_password("password", raise_exception=False)

	if not all([cfg.server_ip, cfg.server_port, cfg.username, password]):
		frappe.throw(
			_("Please configure server IP, port, username and password in {0}.").format(ZKTECO_CONFIG)
		)

	url = build_url(cfg, "api-token-auth/")

	try:
		response = requests.post(
			url,
			json={"username": cfg.username, "password": password},
			timeout=REQUEST_TIMEOUT,
		)
		response.raise_for_status()
		token = (response.json() or {}).get("token")
	except ValueError:
		frappe.throw(_("The device returned an invalid JSON response."))
	except requests.RequestException as e:
		frappe.throw(_("Connection error: {0}").format(str(e)), title=_("ZKTeco Device Unreachable"))

	if not token:
		frappe.throw(_("Token not found in the device response."))

	cfg.token = token
	cfg.save()

	# The token is deliberately not returned to the browser: it is a Password field and is
	# only ever handed to the device over the wire.
	return {"success": True, "message": _("API token registered successfully.")}


@frappe.whitelist()
def test_connection():
	"""Verify the stored token and preview today's transactions."""
	frappe.only_for(ALLOWED_ROLES)

	cfg = get_config()
	token = get_token(cfg)

	if not token:
		return {
			"ok": False,
			"error": _("No API token configured. Use 'Register API token' first."),
		}

	if not (cfg.server_ip and cfg.server_port):
		return {"ok": False, "error": _("Please configure the server IP and port first.")}

	day = today()
	params = {
		"start_time": f"{day} 00:00:00",
		"end_time": f"{day} 23:59:59",
	}

	try:
		transactions, total = request_transactions(cfg, token, params)
	except ValueError:
		return {
			"ok": False,
			"error": _("The device returned an invalid JSON response."),
		}
	except requests.RequestException as e:
		return {"ok": False, "error": _("Connection error: {0}").format(str(e))}

	return {
		"ok": True,
		"url": build_url(cfg, "iclock/api/transactions/"),
		"total_transactions": total,
		"transactions_preview": build_transaction_preview(transactions[:5]),
		"message": _("Found {0} transactions for {1}").format(total, day),
	}


@frappe.whitelist(methods=["POST"])
def manual_sync():
	"""Run a sync on demand and report what happened."""
	frappe.only_for(ALLOWED_ROLES)

	try:
		result = sync_zkteco_transactions(commit=True)
	except Exception as e:
		frappe.log_error(
			title=_("ZKTeco Manual Sync"),
			message=frappe.get_traceback(),
		)
		frappe.throw(_("Sync failed: {0}").format(str(e)), title=_("ZKTeco Sync Failed"))

	return {"success": True, "message": _("Sync completed."), **result}


@frappe.whitelist()
def get_sync_status():
	"""Return the current configuration and sync statistics."""
	frappe.only_for(ALLOWED_ROLES)

	try:
		cfg = get_config()
		recent_checkins = frappe.db.count(
			"Employee Checkin",
			{"device_id": ["like", "%ZKTeco%"], "creation": [">=", now_datetime() - timedelta(days=1)]},
		)

		return {
			"enabled": bool(cfg.enable_sync),
			"sync_frequency": cint(cfg.seconds) or DEFAULT_SYNC_SECONDS,
			"last_sync": cfg.last_sync,
			"recent_checkins_24h": recent_checkins,
			"server_configured": bool(cfg.server_ip and cfg.server_port),
			"token_configured": bool(get_token(cfg)),
		}
	except Exception:
		frappe.log_error(title=_("ZKTeco Sync Status"), message=frappe.get_traceback())
		return {"error": _("Could not read the current sync status.")}


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


def build_transaction_preview(transactions: list) -> list:
	"""Format transactions for the 'Test Connection' dialog."""
	preview = []

	for transaction in transactions:
		emp_code = transaction.get("emp_code")
		employee_name = " ".join(
			filter(None, [transaction.get("first_name") or "", transaction.get("last_name") or ""])
		)
		employee = find_employee_by_code(emp_code) if emp_code else None

		preview.append(
			{
				"id": transaction.get("id"),
				"employee_code": emp_code,
				"employee_name": employee_name,
				"mapped_employee": employee,
				"punch_time": transaction.get("punch_time"),
				"log_type": map_log_type(
					transaction.get("punch_state"), transaction.get("punch_state_display")
				),
				"device_id": transaction.get("terminal_alias") or transaction.get("terminal_sn"),
				"verify_method": transaction.get("verify_type_display"),
			}
		)

	return preview


def sync_zkteco_transactions(commit: bool = False) -> dict:
	"""Pull new device punches and create the matching `Employee Checkin` records."""
	cfg = get_config()

	if not cfg.enable_sync:
		frappe.logger("zkteco_checkins_sync").info("ZKTeco sync is disabled. Skipping run.")
		return {"processed": 0, "errors": 0, "skipped": True}

	token = get_token(cfg)
	if not token:
		frappe.logger("zkteco_checkins_sync").info("ZKTeco API token is not configured. Skipping run.")
		return {"processed": 0, "errors": 0, "skipped": True}

	start_time, end_time = get_sync_window(cfg)
	params = {
		"start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
		"end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
	}
	transactions, _ = request_transactions(cfg, token, params)

	processed = 0
	errors = 0

	for transaction in transactions:
		try:
			if create_employee_checkin(transaction):
				processed += 1
			else:
				errors += 1
		except Exception:
			errors += 1
			frappe.log_error(
				title=_("ZKTeco Sync"),
				message=frappe.get_traceback(),
				reference_doctype="Employee Checkin",
			)

	frappe.db.set_single_value(ZKTECO_CONFIG, "last_sync", end_time)
	frappe.db.set_single_value(
		ZKTECO_CONFIG, "total_synced_records", cint(cfg.total_synced_records) + processed
	)

	if commit:
		frappe.db.commit()

	frappe.logger("zkteco_checkins_sync").info(
		_("ZKTeco sync completed: {0} processed, {1} errors.").format(processed, errors)
	)

	return {"processed": processed, "errors": errors, "skipped": False}


def create_employee_checkin(transaction: dict) -> bool:
	"""Create an `Employee Checkin` for a single device transaction.

	Returns True when the punch was created or had already been imported, False otherwise.
	"""
	emp_code = transaction.get("emp_code")
	punch_time = transaction.get("punch_time")

	if not emp_code or not punch_time:
		frappe.log_error(
			title=_("ZKTeco Transaction"),
			message=_("Skipping a transaction without emp_code or punch_time: {0}").format(
				json.dumps(transaction, default=str)
			),
		)
		return False

	employee = find_employee_by_code(emp_code)
	if not employee:
		frappe.logger("zkteco_checkins_sync").info(
			_("No ERPNext employee matches device code {0}.").format(emp_code)
		)
		return False

	punch_datetime = get_datetime(punch_time) if isinstance(punch_time, str) else punch_time
	device_id = get_device_id(transaction)
	log_type = map_log_type(transaction.get("punch_state"), transaction.get("punch_state_display"))

	# `device_id` embeds the transaction id, so an identical punch always produces an
	# identical device_id and the existence check is an exact de-duplication.
	if frappe.db.exists("Employee Checkin", {"employee": employee, "device_id": device_id}):
		return True

	try:
		frappe.get_doc(
			{
				"doctype": "Employee Checkin",
				"employee": employee,
				"time": punch_datetime,
				"log_type": log_type,
				"device_id": device_id,
				"skip_auto_attendance": 0,
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			title=_("ZKTeco Checkin Creation"),
			message=frappe.get_traceback(),
			reference_doctype="Employee Checkin",
		)
		return False

	return True


# ---------------------------------------------------------------------------
# Scheduled tasks
# ---------------------------------------------------------------------------


def scheduled_sync():
	"""Cron entry point: sync, but no more often than the configured frequency."""
	cfg = get_config()

	if not cfg.enable_sync:
		return

	interval = max(cint(cfg.seconds) or DEFAULT_SYNC_SECONDS, MIN_SYNC_SECONDS)

	# Throttle on Redis rather than on the document, so a failed run cannot get stuck and
	# the timer survives `bench migrate`. `expires=True` skips the per-request local cache.
	if frappe.cache().get_value(THROTTLE_KEY, expires=True):
		return

	frappe.cache().set_value(THROTTLE_KEY, now_datetime(), expires_in_sec=interval)

	try:
		sync_zkteco_transactions(commit=True)
	except Exception:
		frappe.log_error(title=_("ZKTeco Scheduled Sync"), message=frappe.get_traceback())


def cleanup_scheduler_check():
	"""Daily heartbeat, so there is a trace in the logs that the job is alive."""
	try:
		cfg = get_config()
		if cfg.enable_sync:
			frappe.logger("zkteco_checkins_sync").info(
				_("ZKTeco scheduler is active. Last sync: {0}").format(cfg.last_sync or _("never"))
			)
	except Exception:
		frappe.log_error(title=_("ZKTeco Scheduler Check"), message=frappe.get_traceback())
