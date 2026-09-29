// Copyright (c) 2025, osama.ahmed@deliverydevs.com and contributors
// For license information, please see license.txt

frappe.ui.form.on("ZKTeco Config", {
	refresh(frm) {
		// `token` is a Password field, so its value is masked in the form. Ask the server
		// what state the sync is actually in instead of inspecting the document.
		load_sync_status(frm);

		if (frm.doc.enable_sync) {
			frm.add_custom_button(__("Manual Sync"), () => manual_sync(frm), __("Actions"));
			frm.add_custom_button(__("Sync Status"), () => show_sync_status(frm), __("Actions"));
		}
	},

	enable_sync(frm) {
		if (frm.doc.enable_sync) {
			frappe.show_alert({
				message: __("ZKTeco sync enabled. Configure the server settings and test the connection."),
				indicator: "blue"
			});
			load_sync_status(frm);
		}
	},

	test_connection(frm) {
		frappe.call({
			method: "zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config.zkteco_config.test_connection",
			freeze: true,
			freeze_message: __("Testing connection...")
		})
			.then((r) => {
				const msg = r.message || {};

				if (msg.ok) {
					frappe.show_alert({
						message: __("Connected successfully! Found {0} transactions today.", [msg.total_transactions || 0]),
						indicator: "green"
					});

					if (msg.transactions_preview && msg.transactions_preview.length) {
						show_transaction_preview(msg.transactions_preview, msg.total_transactions || 0);
					}
					return;
				}

				frappe.msgprint({
					title: __("Connection Error"),
					message: `<pre class="text-danger" style="white-space:pre-wrap;">${escape(msg.error)}</pre>`,
					indicator: "red"
				});
			})
			.catch((e) => show_error(__("Error"), e));
	},

	register_api_token(frm) {
		frappe.call({
			method: "zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config.zkteco_config.register_api_token",
			freeze: true,
			freeze_message: __("Registering token...")
		})
			.then((r) => {
				const msg = r.message || {};

				// The token is stored server side and never sent back to the browser.
				frm.reload_doc().then(() => {
					frappe.show_alert({
						message: msg.message || __("API token registered and saved successfully."),
						indicator: "green"
					});
				});
			})
			.catch((e) => show_error(__("Token Registration Failed"), e));
	}
});

function escape(value) {
	if (value === null || value === undefined) {
		return "";
	}
	return frappe.utils.escape_html(String(value));
}

function show_error(title, e) {
	frappe.msgprint({
		title: title,
		message: `<pre class="text-danger" style="white-space:pre-wrap;">${escape((e && e.message) || e)}</pre>`,
		indicator: "red"
	});
}

function load_sync_status(frm) {
	frappe.call({
		method: "zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config.zkteco_config.get_sync_status"
	})
		.then((r) => {
			const status = r.message || {};
			show_sync_indicator(frm, status);
		})
		.catch(() => frm.dashboard.clear_headline());
}

function show_sync_indicator(frm, status) {
	frm.dashboard.clear_headline();

	if (!frm.doc.enable_sync) {
		frm.dashboard.add_indicator(__("Sync Disabled"), "red");
		return;
	}

	if (status.error) {
		frm.dashboard.add_indicator(__("Sync Status Unavailable"), "orange");
		return;
	}

	if (!status.server_configured) {
		frm.dashboard.add_indicator(__("Server Not Configured"), "orange");
		return;
	}

	if (!status.token_configured) {
		frm.dashboard.add_indicator(__("Token Missing"), "orange");
		return;
	}

	frm.dashboard.add_indicator(
		__("Sync Active (every {0}s)", [status.sync_frequency || 300]),
		"green"
	);
}

function show_transaction_preview(transactions, total_count) {
	const rows = transactions
		.map((txn) => {
			const mapped = txn.mapped_employee
				? `<span class="text-success">${__("Mapped")}</span>`
				: `<span class="text-warning">${__("Not Found")}</span>`;
			const log_type =
				txn.log_type === "IN"
					? `<span class="text-primary"><b>${escape(txn.log_type)}</b></span>`
					: `<span class="text-danger"><b>${escape(txn.log_type)}</b></span>`;

			return `<tr>
				<td>${escape(txn.id || __("N/A"))}</td>
				<td>
					<b>${escape(txn.employee_code || __("N/A"))}</b><br>
					<small class="text-muted">${escape(txn.employee_name || __("Unknown"))}</small>
				</td>
				<td>${escape(txn.punch_time)}</td>
				<td>${log_type}</td>
				<td>${escape(txn.device_id || __("Unknown"))}</td>
				<td>${mapped}</td>
			</tr>`;
		})
		.join("");

	const html = `
		<div class="mb-3">
			<b>${__("Found {0} transactions today", [total_count])}</b><br>
			<small class="text-muted">${__("Showing the latest {0} transactions:", [transactions.length])}</small>
		</div>
		<div style="max-height: 400px; overflow-y: auto;">
			<table class="table table-bordered table-striped" style="font-size: 12px;">
				<thead>
					<tr>
						<th>${__("ID")}</th>
						<th>${__("Employee")}</th>
						<th>${__("Time")}</th>
						<th>${__("Type")}</th>
						<th>${__("Device")}</th>
						<th>${__("ERPNext Status")}</th>
					</tr>
				</thead>
				<tbody>${rows}</tbody>
			</table>
		</div>
		<div class="alert alert-info" style="margin-top: 15px;">
			<small>
				<b>${__("Tips")}</b><br>
				${__("• Employee codes in ERPNext must match the emp_code reported by the device.")}<br>
				${__("• Transactions marked “Not Found” are skipped.")}<br>
				${__("• Enable sync and set a frequency to import punches automatically.")}
			</small>
		</div>`;

	new frappe.ui.Dialog({
		title: __("ZKTeco Transactions Preview"),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "transaction_preview",
				options: html
			}
		],
		size: "large"
	}).show();
}

function manual_sync(frm) {
	frappe.call({
		method: "zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config.zkteco_config.manual_sync",
		freeze: true,
		freeze_message: __("Syncing transactions...")
	})
		.then((r) => {
			const msg = r.message || {};

			if (msg.skipped) {
				frappe.show_alert({
					message: __("Sync skipped: enable sync and register an API token first."),
					indicator: "orange"
				});
			} else {
				frappe.show_alert({
					message: __("Sync finished: {0} imported, {1} skipped.", [msg.processed || 0, msg.errors || 0]),
					indicator: (msg.errors || 0) ? "orange" : "green"
				});
			}

			frm.reload_doc();
		})
		.catch((e) => show_error(__("Manual Sync Failed"), e));
}

function show_sync_status(frm) {
	frappe.call({
		method: "zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config.zkteco_config.get_sync_status"
	})
		.then((r) => {
			const status = r.message || {};

			if (status.error) {
				frappe.msgprint({
					title: __("ZKTeco Sync Status"),
					message: `<span class="text-danger">${escape(status.error)}</span>`,
					indicator: "orange"
				});
				return;
			}

			const rows = [
				[__("Sync Enabled"), status.enabled ? __("Yes") : __("No")],
				[__("Sync Frequency"), __("Every {0} seconds", [status.sync_frequency || "-"])],
				[__("Last Sync"), status.last_sync || __("Never")],
				[__("Recent Check-ins (24h)"), status.recent_checkins_24h || 0],
				[__("Server Configured"), status.server_configured ? __("Yes") : __("No")],
				[__("Token Configured"), status.token_configured ? __("Yes") : __("No")]
			]
				.map(([label, value]) => `<tr><td><b>${escape(label)}</b></td><td>${escape(value)}</td></tr>`)
				.join("");

			frappe.msgprint({
				title: __("ZKTeco Sync Status"),
				message: `<table class="table table-bordered">${rows}</table>`,
				indicator: status.enabled && status.token_configured ? "green" : "orange"
			});
		})
		.catch((e) => show_error(__("ZKTeco Sync Status"), e));
}
