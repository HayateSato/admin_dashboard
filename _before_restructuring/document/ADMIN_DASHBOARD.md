# Admin Dashboard Updates - Final Configuration

## Changes Made (2025-11-20)

### 1. Updated K-Value Options ✅

**Changed from**: [5, 10, 15, 20, 30]
**Changed to**: [2, 3, 5, 10, 15, 20]

**Location**: `templates/registered_patients.html` line 180

```javascript
const kValues = [2, 3, 5, 10, 15, 20];
```

**Behavior**:
- Admin can only select K-values **higher than** current value
- Lower/equal values are **disabled and greyed out**
- If current K-value is already the highest (20), all lower options disabled

---

### 2. Updated Time Window Options ✅

**Changed from**: [5s, 10s, 15s, 30s, 60s, 120s, 300s]
**Changed to**: [5s, 10s, 15s, 20s, 30s]

**Location**: `templates/registered_patients.html` line 189

```javascript
const timeWindows = [5, 10, 15, 20, 30];
```

**Behavior**:
- All values are selectable (no restrictions)
- Displayed as dropdown, not up/down arrow buttons

---

### 3. Remote Anonymization Control ✅

**Status**: **Read-only** (cannot be changed by admin)

**Removed**:
- Toggle switch from patient table
- `toggleRemoteAnon()` function
- Admin ability to enable/disable remote anonymization

**Displayed as**: Status badge only
- Green "Enabled" badge when patient has enabled it
- Grey "Disabled" badge when patient has disabled it

**Rationale**:
- Remote anonymization requires **patient consent**
- Only the patient can enable/disable this in their Flutter app
- Admin can view status but cannot change it

---

### 4. Auto Anonymization Setting ✅

**Status**: **Read-only** (removed from admin controls)

**Display**: Icon in table (checkmark or X)
- ✓ Green checkmark: Auto anonymization enabled
- ✗ Grey X: Auto anonymization disabled

**Note**: This setting is managed by the patient in their Flutter app

---

### 5. Updated Info Banner ✅

**New text**:
```
ℹ️ Admin Controls: You can adjust K-Value (2,3,5,10,15,20 - only higher values) and
Time Window (5s,10s,15s,20s,30s) for patients only when Remote Anonymization is
enabled by the patient. Select new values from the dropdowns and click Apply to send
via MQTT.

Important: Remote Anonymization must be enabled by the patient in their Flutter app.
Admin cannot enable/disable this setting.
```

---

## Business Rules Summary

### Admin Can:
1. **View** all patients and their settings
2. **Adjust K-Value** (only to higher values) when remote anon is enabled
3. **Adjust Time Window** (any value from list) when remote anon is enabled
4. **Send settings** via MQTT when remote anon is enabled

### Admin Cannot:
1. ~~Enable/disable Remote Anonymization~~ (patient controls this)
2. ~~Enable/disable Auto Anonymization~~ (patient controls this)
3. ~~Lower K-Value~~ (only higher values allowed for security)
4. ~~Change settings when Remote Anon is disabled~~ (would be ignored anyway)

### Patient Controls (in Flutter App):
1. **Remote Anonymization** - Enable/disable admin access
2. **Auto Anonymization** - Enable/disable automatic processing
3. **K-Value** - Set initial value (2, 3, 5, 10, 15, 20)
4. **Time Window** - Set initial value (5s, 10s, 15s, 20s, 30s)

---

## How It Works

### Scenario 1: Patient Enables Remote Anonymization

1. **Patient** enables "Remote Anonymization" in Flutter app
2. **Flutter app** updates PostgreSQL: `privacy_policies.is_remote = true`
3. **Admin dashboard** shows "Enabled" badge (green) for that patient
4. **Admin** can now:
   - Select new K-value (only higher than current)
   - Select new time window (any value)
   - Click "Apply" button
5. **Settings sent** via MQTT to patient's device
6. **Patient's Flutter app** receives settings and applies them
7. **Database updated** with new settings

### Scenario 2: Patient Disables Remote Anonymization

1. **Patient** disables "Remote Anonymization" in Flutter app
2. **Flutter app** updates PostgreSQL: `privacy_policies.is_remote = false`
3. **Admin dashboard** shows "Disabled" badge (grey) for that patient
4. **Admin** can still see the patient and their current settings
5. **Admin** can still change dropdowns, but:
   - Apply button still works (sends MQTT message)
   - **Flutter app will ignore** the message (remote anon disabled)
   - No settings will be changed on device

**Note**: The admin dashboard doesn't prevent sending when remote anon is disabled, but the Flutter app will reject the command.

---

## Table Layout

| Column | Type | Admin Control | Patient Control |
|--------|------|---------------|-----------------|
| Unique Key | Text | View only | N/A |
| Device ID | Text | View only | N/A |
| Last Session | Timestamp | View only | N/A |
| **K-Value** | **Dropdown** | **Editable (↑ only)** | **Initial value** |
| **Time Window** | **Dropdown** | **Editable** | **Initial value** |
| Auto Anon | Icon | View only | Enable/Disable |
| Remote Anon | Badge | **View only** | **Enable/Disable** |
| Actions | Apply button | Send via MQTT | N/A |

Legend:
- **Bold** = Key settings
- ↑ = Only higher values
- View only = Cannot change
- N/A = Not applicable

---

## MQTT Communication

### Settings Update Message

**Topic**: `privacy/settings/{unique_key}`

**Payload**:
```json
{
  "unique_key": "0000000000...",
  "k_value": 15,
  "time_window": 20,
  "auto_anonymize": true,
  "timestamp": "2025-11-20T10:30:00.000Z",
  "source": "admin_dashboard"
}
```

**QoS**: 1 (guaranteed delivery)

### Flutter App Response

**Checks**:
1. Is remote anonymization enabled? (Check local setting + PostgreSQL)
2. Is K-value higher than current? (Security check)
3. Is time window valid? (5, 10, 15, 20, 30)

**If all checks pass**:
- Apply new settings
- Update local storage
- Update PostgreSQL
- Send acknowledgment: `privacy/{unique_key}/ack`

**If any check fails**:
- Reject command
- Log error
- Send error acknowledgment

---

## Files Modified

### Admin Dashboard

**File**: `templates/registered_patients.html`
- Line 56-58: Updated info banner
- Line 180: Updated K-value options [2, 3, 5, 10, 15, 20]
- Line 189: Updated time window options [5, 10, 15, 20, 30]
- Removed: Remote anon toggle switch
- Removed: Auto anon dropdown

---

## Testing Checklist

### Admin Dashboard

- [ ] K-value dropdown shows [2, 3, 5, 10, 15, 20]
- [ ] Time window dropdown shows [5s, 10s, 15s, 20s, 30s]
- [ ] Lower K-values are disabled and greyed out
- [ ] Current K-value is selected by default
- [ ] Apply button appears when values change
- [ ] Apply button sends MQTT message
- [ ] Remote Anon column shows badge only (no toggle)
- [ ] Auto Anon column shows icon only (no dropdown)
- [ ] Info banner explains admin controls clearly

### Flutter App (Separate Document)

See: `FLUTTER_POSTGRES_CONNECTION_FIX.md` for Flutter-side fixes

---

## Deployment

### Dashboard

```bash
cd C:\Users\HayateSato\AndroidStudioProjects\Demonstrator\admin_dashbaord
docker restart privacy_umbrella_dashboard
```

Dashboard is now live with updated settings at: http://localhost:5000

### Flutter App

Requires code changes in:
- `lib/src/postgres/postgres_handler.dart` - Fix connection check
- `lib/src/screens/settings/anonymization_settings.dart` - Ensure connection maintained

See: `FLUTTER_POSTGRES_CONNECTION_FIX.md` for detailed fix

---

**Updated**: 2025-11-20
**Status**: Dashboard ✅ Complete | Flutter App ⚠️ Needs Fix
**Impact**: Improved security model, clearer admin boundaries
