app_name = "zkteco_checkins_sync"
app_title = "ZKTeco Checkin Sync"
app_publisher = "osama.ahmed@deliverydevs.com"
app_description = "This app pulls transactions from ZKTeco devices and creates Employee Checkin records."
app_email = "osama.ahmed@deliverydevs.com"
app_license = "mit"

# Apps
# ------------------

# `Employee` ships with ERPNext and `Employee Checkin` ships with HRMS (as of v16 it is no
# longer part of ERPNext's `hr` module). Both must be installed before this app.
required_apps = ["erpnext", "hrms"]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/zkteco_checkins_sync/css/zkteco_checkins_sync.css"
# app_include_js = "/assets/zkteco_checkins_sync/js/zkteco_checkins_sync.js"

# include js, css files in header of web template
# web_include_css = "/assets/zkteco_checkins_sync/css/zkteco_checkins_sync.css"
# web_include_js = "/assets/zkteco_checkins_sync/js/zkteco_checkins_sync.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "zkteco_checkins_sync/public/scss/website"

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "zkteco_checkins_sync/public/icons.svg"

# Home Pages
# ----------

# Installation
# ------------

# before_install = "zkteco_checkins_sync.install.before_install"
# after_install = "zkteco_checkins_sync.install.after_install"

# Uninstallation
# --------------

# before_uninstall = "zkteco_checkins_sync.uninstall.before_uninstall"
# after_uninstall = "zkteco_checkins_sync.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "zkteco_checkins_sync.utils.before_app_install"
# after_app_install = "zkteco_checkins_sync.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "zkteco_checkins_sync.utils.before_app_uninstall"
# after_app_uninstall = "zkteco_checkins_sync.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "zkteco_checkins_sync.notifications.get_notification_config"

# Permissions
# -----------

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------
# IMPORTANT: `scheduler_events` must stay a static literal. Frappe imports this module at
# `frappe.init()` time (before the site database is connected) and caches the result, so
# querying `ZKTeco Config` here is unreliable and breaks `bench build`, `bench new-site` and
# `bench migrate`. The sync interval configured by the user is therefore applied at runtime
# inside `scheduled_sync`, which throttles itself using the configured frequency.

scheduler_events = {
	"cron": {
		"* * * * *": [
			"zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config.zkteco_config.scheduled_sync"
		]
	},
	"daily": [
		"zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config.zkteco_config.cleanup_scheduler_check"
	],
}

# Testing
# -------

# before_tests = "zkteco_checkins_sync.install.before_tests"

# Overriding Methods
# ------------------------------

# exempt linked doctypes from being automatically cancelled
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Request Events
# ----------------
# before_request = ["zkteco_checkins_sync.utils.before_request"]
# after_request = ["zkteco_checkins_sync.utils.after_request"]

# Job Events
# ----------
# before_job = ["zkteco_checkins_sync.utils.before_job"]
# after_job = ["zkteco_checkins_sync.utils.after_job"]

# User Data Protection
# --------------------

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"zkteco_checkins_sync.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True
