# Central Anonymization Command Line Argument Fix

## Issue

Central anonymization jobs were failing with the error:
```
central_anonymizer.py: error: unrecognized arguments: --end_time 2025-11-19
```

## Root Cause

The `anonymization_manager.py` file was passing `--end_time` (with underscore) to the central anonymizer script, but the script expected `--end-time` (with hyphen).

**Error log showed**:
```
Command: /opt/venv/bin/python /app/modules/utils_central_anon/central_anonymizer.py
         --k-value 5 --time-window 60 --unique-key 0000...
         --start-time 2025-11-18 --end_time 2025-11-19  <-- WRONG
         --output-format csv
```

**Expected format**:
```
--start-time 2025-11-18 --end-time 2025-11-19  <-- CORRECT
```

## Fix Applied

**File**: `modules/anonymization_manager.py`
**Line**: 377

**Before**:
```python
cmd.extend(['--end_time', job['end_time']])  # Wrong: underscore
```

**After**:
```python
cmd.extend(['--end-time', job['end_time']])  # Correct: hyphen
```

## Deployment

1. Fixed the local source file
2. Rebuilt Docker container **without cache** to ensure latest code:
   ```bash
   docker-compose down
   docker-compose build --no-cache admin_dashboard
   docker-compose up -d
   ```

3. Verified fix in running container:
   ```bash
   docker exec privacy_umbrella_dashboard sh -c \
     "grep 'cmd.extend.*end' /app/modules/anonymization_manager.py"
   ```

   Result: `cmd.extend(['--end-time', job['end_time']])` ✅

## Testing

Try running a central anonymization job again:
1. Navigate to **Central Anonymization** page
2. Enter patient information or unique key
3. Configure anonymization settings (K-value, time window, output format)
4. Add date range (start and end time)
5. Click "Start Anonymization"

Expected: Job should run successfully without argument errors.

## Related Arguments

All command line arguments use **hyphens** (not underscores):
- `--k-value` ✅
- `--time-window` ✅
- `--unique-key` ✅
- `--start-time` ✅
- `--end-time` ✅ (now fixed)
- `--output-format` ✅
- `--api-server` ✅
- `--api-port` ✅
- `--max-records` ✅

## Status

✅ **Fixed** - Container rebuilt with correct argument format
📅 **Date**: 2025-11-25
🔍 **Verified**: Command now uses `--end-time` with hyphen
