# ZKTeco Checkin Sync - Installation & Setup Guide

## Overview
This Frappe app automatically synchronizes employee check-in/check-out transactions from ZKTeco biometric devices with ERPNext/HRMS Employee Checkin records.

## Version compatibility

| App version | Frappe | Notes |
|-------------|--------|-------|
| `1.0.0` (current) | **v16** | Requires ERPNext v16 **and** HRMS v16 |
| `0.0.1` (legacy) | v15 | Not supported on v16; upgrade first |

> **Important for v16:** `Employee Checkin` is no longer part of ERPNext. It now ships with
> **HRMS** (module `HR`). ERPNext v16 has no `hr` module at all. `Employee` itself now lives in
> ERPNext's `Setup` module. This app therefore declares `required_apps = ["erpnext", "hrms"]`
> and will refuse to install without both.

## Features
- **Real-time Sync**: Configurable sync frequency (10 seconds to 1 hour)
- **Smart Mapping**: Automatically maps ZKTeco employee codes to ERPNext employees
- **Duplicate Prevention**: Prevents duplicate check-in records
- **Test Connection**: Preview transactions before enabling sync
- **Adaptive Scheduler**: A single every-minute cron job throttles itself to your configured frequency
- **Paginated Import**: Follows the device's pagination so large days import completely
- **Role-protected**: Every API is restricted to System Manager / HR Manager / HR User
- **Secure Credentials**: Superuser password and API token are stored encrypted
- **Comprehensive Logging**: Detailed error tracking and sync statistics

## Prerequisites

### ZKTeco Device Requirements
- ZKBio Time software installed and running
- Device connected to network
- API access enabled
- Superuser credentials available

### Framework Requirements
- Frappe **v16** (bench running Python 3.14+ and Node 24+)
- ERPNext **v16**
- HRMS **v16** (provides the `Employee Checkin` doctype)
- Employee records with matching employee codes
- The background **scheduler** enabled on the site, otherwise nothing syncs automatically

## Installation

### On a bench
```bash
cd /path/to/your/bench

bench get-app erpnext --branch version-16
bench get-app hrms --branch version-16
bench get-app zkteco_checkins_sync

bench --site your-site.com install-app erpnext
bench --site your-site.com install-app hrms
bench --site your-site.com install-app zkteco_checkins_sync

bench --site your-site.com migrate
bench build
```

### On Frappe Cloud
1. Make sure **ERPNext** and **HRMS** are installed on the site.
2. Install the app from the marketplace / app manager, or push it to the bench.
3. Open the app, fill in the settings below, and click **Register API token**.

> Cloud note: the app talks outbound to your ZKTeco device, so the device must be reachable
> from the Cloud bench (public IP, VPN or tunnel). A device on a private LAN will not be
> reachable from Cloud unless you expose it.

### 2. Setup ZKTeco Device

#### Configure ZKBio Time
1. Open ZKBio Time software
2. Go to **System Settings** → **Communication**
3. Note down the **Server IP** and **Port** (usually port 80)
4. Ensure API access is enabled
5. Create or note superuser credentials

#### Test Device Connectivity
```bash
# Test if device is accessible
curl -X GET "http://[DEVICE_IP]:[PORT]/iclock/api/transactions/"
```

## Configuration

### 1. Access ZKTeco Config
1. Login to the desk
2. Search for **ZKTeco Config** in the global search (it is a Single DocType)
3. Enable sync: check **"Enable Sync"**

### 2. Configure Connection Settings

#### ZKTeco Superuser Credentials
- **Username**: Your ZKBio Time superuser username
- **Password**: Your ZKBio Time superuser password

#### ZKTeco API Credentials
- **Server IP**: IP address of the ZKBio Time server (e.g., 192.168.1.100)
- **Server Port**: Port number (usually 80)

### 3. Register API Token
1. Fill in Server IP and Port
2. Click **"Register API token"**
3. Token will be automatically generated and saved

### 4. Test Connection
1. Click **"Test Connection"** button
2. Review the transaction preview
3. Verify employee mappings

### 5. Configure Sync Settings
- **Sync Frequency**: Choose from 10 seconds to 1 hour
  - **10-30 seconds**: For real-time monitoring
  - **5-15 minutes**: Recommended for most setups
  - **30+ minutes**: For less frequent updates

## Employee Mapping

### Automatic Mapping
The system automatically maps ZKTeco employees to ERPNext using:

1. **Employee ID** field in ERPNext matches `emp_code` from ZKTeco
2. **User ID** field in ERPNext matches `emp_code` from ZKTeco
3. **Attendance Device ID** field (if custom field exists)

### Setup Employee Mapping

#### Method 1: Using Employee ID
```
ERPNext Employee → Employee ID = ZKTeco emp_code
Example: Employee ID = "001" matches ZKTeco emp_code = "001"
```

#### Method 2: Using User ID
```
ERPNext Employee → User ID = ZKTeco emp_code
Example: User ID = "E001" matches ZKTeco emp_code = "E001"
```

#### Method 3: Attendance Device ID
ERPNext v14+ ships an `attendance_device_id` field on Employee. Set it to the `emp_code`
reported by the device. No custom field is needed.

## Testing & Verification

### 1. Test Connection
```javascript
// The test will show:
✅ Connection status
📊 Number of transactions found today
👥 Employee mappings (Found/Not Found)
🔍 Sample transaction data
```

### 2. Manual Sync
1. Go to ZKTeco Config
2. Click **Actions** → **Manual Sync**
3. Check Employee Checkin list for new records

### 3. Monitor Sync Status
1. Click **Actions** → **Sync Status**
2. Review:
   - Last sync time
   - Recent check-ins count
   - Configuration status

## Transaction Data Mapping

### ZKTeco API Response Format
```json
{
  "count": 8,
  "data": [
    {
      "id": 2,
      "emp_code": "001",
      "first_name": "John",
      "last_name": "Doe",
      "punch_time": "2025-08-15 17:54:17",
      "punch_state": "0",  // 0 = Check In, 1 = Check Out
      "punch_state_display": "Check In",
      "terminal_alias": "Main_Entrance"
    }
  ]
}
```

### ERPNext Employee Checkin Mapping
```python
ZKTeco Field           → ERPNext Field
emp_code              → employee (via mapping)
punch_time            → time
punch_state ("0"/"1") → log_type ("IN"/"OUT")
terminal_alias        → device_id
id                    → device_id (appended for uniqueness)
```

## Troubleshooting

### Common Issues

#### 1. Connection Failed
```
❌ Symptoms: Test connection fails
🔧 Solutions:
- Verify Server IP and Port
- Check network connectivity
- Ensure ZKBio Time is running
- Verify firewall settings
```

#### 2. Token Registration Failed
```
❌ Symptoms: Cannot register API token
🔧 Solutions:
- Check username/password
- Ensure superuser privileges
- Verify API endpoint accessibility
```

#### 3. Employees Not Found
```
❌ Symptoms: Transactions sync but employees not mapped
🔧 Solutions:
- Check Employee ID/User ID mapping
- Verify emp_code format consistency
- Review Employee master data
```

#### 4. Duplicate Check-ins
```
❌ Symptoms: Multiple records for same punch
🔧 Solutions:
- System automatically prevents duplicates
- Check device_id uniqueness
- Review time tolerance settings
```

### Error Logs
Monitor error logs in:
- **Error Log** doctype in ERPNext
- System logs with title "ZKTeco"

### Debug Mode
```python
# Enable detailed logging (v16 keyword arguments)
frappe.log_error(title="ZKTeco Debug", message=frappe.get_traceback())
```

## Advanced Configuration

### Sync Frequency
No code change is needed. `ZKTeco Config → Sync Frequency` is read at runtime by
`scheduled_sync()`, which self-throttles using a Redis key. `scheduler_events` in
`hooks.py` is intentionally a static literal: Frappe imports `hooks.py` before the site
database is connected, so it must never query the database at import time.

### Custom Employee Mapping
Override `find_employee_by_code()` in
`zkteco_checkins_sync/zkteco_checkin_sync/doctype/zkteco_config/zkteco_config.py`
to add your own matching rules.

### Field Customization
Extend `create_employee_checkin()` to map additional ZKTeco fields onto custom fields.

## Performance Optimization

### Recommended Settings
- **Small Office (< 50 employees)**: 30-60 seconds
- **Medium Office (50-200 employees)**: 2-5 minutes  
- **Large Office (200+ employees)**: 5-15 minutes

### Database Optimization
```sql
-- Add indexes for better performance
ALTER TABLE `tabEmployee Checkin` 
ADD INDEX `idx_employee_time` (`employee`, `time`);

ALTER TABLE `tabEmployee Checkin` 
ADD INDEX `idx_device_time` (`device_id`, `time`);
```

## Security Considerations

### API Token Security
- Tokens are stored encrypted in ERPNext
- Regular token rotation recommended
- Limit API access to specific IPs if possible

### Network Security
- Use VPN for remote ZKTeco device access
- Implement firewall rules
- Regular security updates

## Maintenance

### Regular Tasks
1. **Monitor sync status** - Weekly
2. **Review error logs** - Daily
3. **Verify employee mappings** - When adding new employees
4. **Test connection** - After any network changes

### Backup Considerations
- Employee Checkin data is included in ERPNext backups
- ZKTeco Config settings are preserved
- API tokens need re-registration after restore

## Support & Troubleshooting

### Log Files to Check
1. **Error Log** doctype in ERPNext
2. **ZKTeco Sync** error logs
3. **ZKTeco Scheduler** logs

### Performance Monitoring
```python
# Check sync statistics
frappe.call('zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config.zkteco_config.get_sync_status')
```

### Contact Support
For technical support or feature requests:
- Email: osama.ahmed@deliverydevs.com

## Changelog

### Version 1.0.0 — Frappe v16 upgrade
- Rebuilt for Frappe v16 / ERPNext v16; added HRMS as a required app
- **Fixed**: the ZKTeco superuser password was read with `db.get_single_value`, which returns
  the *encrypted* blob, so token registration always sent a garbage password
- **Fixed**: a malformed `frappe.db.get_value(...)` call passed a filter dict as the legacy
  `ignore` argument, silently swallowing errors and always returning `None`
- **Fixed**: duplicate detection compared against the raw device id while check-ins were stored
  with a transaction-id suffix, so every run re-imported the same punches
- **Fixed**: the API token was stored in plain text; it is now a Password field
- **Fixed**: whitelisted methods had no permission check and were callable by any logged-in user
- **Fixed**: `get_scheduler_events()` queried the database at `hooks.py` import time, which
  breaks `bench build`, `bench new-site` and `bench migrate`
- **Fixed**: disabled/unconfigured syncs wrote Error Log rows on every run
- Added transaction pagination for large result sets
- Added a real test suite (23 tests) and updated CI to v16
- Replaced deprecated `FrappeTestCase` with `IntegrationTestCase`

### Version 0.0.1
- Initial release
- Basic sync functionality
- Dynamic scheduler
- Employee mapping
- Error handling and logging
