# Debugging Central Anonymization Unique Key Search

## Problem

When searching for patient data in the Central Anonymization page, no data is found even though data exists in InfluxDB.

## Root Cause

The unique key being searched **doesn't match** the unique keys that actually exist in InfluxDB.

### How Unique Keys Work

1. **Flutter app** generates unique keys from patient personal information using a Bloom Filter algorithm:
   ```
   Input: given_name, family_name, date_of_birth, gender
   Process: Normalize → Hash with seeds → Bloom filter → Hex string
   Output: 64-character hex string (e.g., "0000000000000000000008008000000000000000000000000000000100000000")
   ```

2. **Admin dashboard** generates the same way when you enter personal information

3. **The keys MUST match exactly** for the search to find data

## Why Search is Failing

### When searching by Personal Information:
```
Input: Hayate Sato, 1990-01-01, male
Generated Key: 0000000000000000... (first 16 chars shown in logs)
Result: No match in InfluxDB
```

**Reason**: The personal information you entered doesn't match the personal information that was used to generate the keys in InfluxDB.

### When searching by Unique Key:
```
Input: 0000000000000000000008008000000000000000000000000000000100000000
Result: Should work if this exact key exists in InfluxDB
```

## Your Data

According to your logs, you have these unique keys in **InfluxDB**:
1. `0000000000000000000000000000040040000000000000008000000000000000`
2. `000000000000000000000000000000000000000004000000000000000000c000`
3. `0000000000000001000000000400200000000000000000000000000000000000`
4. `0000000000000000000008008000000000000000000000000000000100000000`

And in **PostgreSQL**:
1. `575e50b792ce26d6b7e7b155fbd7e502a96091b659ba226d7c17a96481561935`
2. `0000000000000000000008008000000000000000000000000000000100000000`
3. `0000000000000001000000000400200000000000000000000000000000000000`
4. `0000000000000000000000000000040040000000000000008000000000000000`

## Solution

### Option 1: Search by Exact Unique Key

1. Go to **Central Anonymization** page
2. Select **"No - I only have their unique key"**
3. Enter one of the actual unique keys from InfluxDB:
   ```
   0000000000000000000008008000000000000000000000000000000100000000
   ```
4. Click **Verify**
5. This should find the data ✅

### Option 2: Find the Correct Personal Information

The personal information that generated these keys is in the **Flutter app**. You need to:

1. Check what personal information was entered in the Flutter app when this data was recorded
2. Use the EXACT same information (case-sensitive for name, exact date format) in the admin dashboard

**Example**:
- If Flutter app used: "hayate" (lowercase), "2000-01-15", "male"
- Admin must use: "hayate", "2000-01-15", "male"
- Even "Hayate" (capitalized) would generate a different key!

## Testing

### Test 1: Verify Unique Key Search Works

```bash
# In admin dashboard, try searching with this key:
0000000000000000000008008000000000000000000000000000000100000000
```

Expected: Should find dates with data

### Test 2: Check What Personal Info Was Used

The Flutter app should have stored this when the data was uploaded. Check:
- Did the Flutter app save the personal info locally?
- What name/DOB/gender was entered in the consent form?

## Key Generation Algorithm (for reference)

Both Flutter and admin dashboard use the same algorithm:

```python
# 1. Normalize inputs
given_name = given_name.strip().lower()  # "Hayate" → "hayate"
family_name = family_name.strip().lower()  # "Sato" → "sato"
gender = gender.strip().lower()  # "Male" → "male"
dob = dob.strip()  # "2000-01-15"

# 2. Create pipe-separated string
user_data = f"{given_name}|{family_name}|{dob}|{gender}"
# Example: "hayate|sato|2000-01-15|male"

# 3. Apply 3 hash functions with seeds (0, 1, 2)
# 4. Create 256-bit Bloom filter
# 5. Convert to 64-character hex string
```

## Common Mistakes

❌ **Wrong**: Using "Hayate" when Flutter used "hayate"
❌ **Wrong**: Using "2000-1-15" when Flutter used "2000-01-15"
❌ **Wrong**: Using "M" when Flutter used "male"
❌ **Wrong**: Extra spaces in name

✅ **Correct**: Exact match including case and format

## Recommended Action

**For now**: Use **Option 1** (search by unique key) to test central anonymization:

1. Select "No - I only have their unique key"
2. Enter: `0000000000000000000008008000000000000000000000000000000100000000`
3. Click Verify
4. Select date range
5. Configure K-value and output
6. Start anonymization

This should work immediately.

**For later**: Document the personal information used in Flutter app for testing purposes (in a secure location).

## Verification

After using the unique key search, you should see:
```
✓ Data Found for Unique Key!
Unique Key: 00000000000000000000080080000000...
Total Records: X date(s)
```

Then you can proceed with anonymization configuration.

---

**Status**: ✅ Identified root cause
**Next Step**: Try searching with actual unique key from InfluxDB
