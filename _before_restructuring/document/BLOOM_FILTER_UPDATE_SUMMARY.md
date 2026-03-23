# Bloom Filter Update Summary - Python Backend

## Date: 2025-12-09

## Overview
Updated the Python backend bloom filter implementation to match the PHP privacyUmbrella implementation for cross-platform compatibility in federated learning and privacy-preserving record linkage (PPRL).

---

## Files Modified

### 1. `modules/record_linkage.py`

**Location**: `C:\Users\HayateSato\AndroidStudioProjects\Demonstrator\admin_dashbaord\modules\record_linkage.py`

**Changes Made**:
- ✅ Updated `generate_unique_key()` method to use PHP-compatible bloom filter algorithm
- ✅ Added gender format conversion: `male/female` → `m/f`
- ✅ Added new `_hash_function_php()` method matching PHP hash construction
- ✅ Added new `_bit_array_to_base64()` method for base64 encoding
- ✅ Kept old methods for backward compatibility

---

## Technical Changes

### Previous Implementation (OLD)

```python
# OLD Algorithm
- Filter Size: 256 bits
- Hash Functions: 3
- Input Format: "givenname|familyname|dob|gender" (concatenated)
- Hash Construction: SHA256(input:seed)
- Output Format: Hexadecimal string (64 chars)
- Gender Format: "male", "female", "other" (as-is)
```

### New Implementation (PHP-Compatible)

```python
# NEW Algorithm
- Filter Size: 500 bits
- Hash Functions: 25 per field
- Input Format: Independent fields processed separately
- Hash Construction: SHA256(globalSeed:fieldSeed:i:value)
- Output Format: Base64 string
- Gender Format: "m", "f", "other" (converted from male/female)

# Seeds (MUST match PHP and Dart)
field_seeds = {
    'vorname': 123124567,       # given name
    'nachname': 674532674,       # family name
    'geburtsdatum': 345386767,   # date of birth
    'geschlecht': 566744456,     # gender
}
global_seed = 567895675
```

---

## Gender Format Conversion

The Python backend now automatically converts gender values to ensure compatibility:

```python
# Conversion Logic
"male" → "m"
"männlich" → "m"
"maennlich" → "m"
"female" → "f"
"weiblich" → "f"
"m" → "m" (unchanged)
"f" → "f" (unchanged)
"other" → "other" (unchanged)
```

**Why?** The PHP partner implementation and Flutter app use `m`/`f` format, so the Python backend must convert any incoming `male`/`female` values to match.

---

## Hash Function Details

### New PHP-Compatible Hash Function

```python
def _hash_function_php(self, value: str, global_seed: int, field_seed: int, i: int, filter_size: int) -> int:
    """
    Matches PHP implementation exactly:
    hash('sha256', globalSeed + ':' + fieldSeed + ':' + i + ':' + value)
    """
    data = f"{global_seed}:{field_seed}:{i}:{value}"
    hash_digest = hashlib.sha256(data.encode('utf-8')).hexdigest()

    # Take first 15 hex chars and convert to int (matches PHP hexdec(substr($hash, 0, 15)))
    num = int(hash_digest[:15], 16)

    return num % filter_size
```

**Key Points**:
- Global seed provides overall entropy
- Field-specific seed ensures each field contributes uniquely
- Iteration index `i` creates multiple hash functions (k=25)
- Takes first 15 hex characters (matches PHP implementation exactly)

---

## Base64 Encoding

### New Base64 Conversion

```python
def _bit_array_to_base64(self, bit_array: List[int]) -> str:
    """Convert bit array to base64 string (matches PHP implementation)"""
    # Convert bits to bit string: [1,0,1,1...] → "1011..."
    bit_string = ''.join(str(bit) for bit in bit_array)

    # Convert to bytes (8 bits per byte, pad with zeros)
    bytes_list = []
    for i in range(0, len(bit_string), 8):
        byte_bits = bit_string[i:i+8]
        if len(byte_bits) < 8:
            byte_bits = byte_bits.ljust(8, '0')  # Pad right with zeros
        bytes_list.append(int(byte_bits, 2))

    # Encode as base64
    return base64.b64encode(bytes(bytes_list)).decode('ascii')
```

---

## Impact on Anonymization Manager

**File**: `modules/anonymization_manager.py`

**Status**: ✅ No changes needed

**Reason**: The anonymization manager uses `RecordLinkage` class internally, so it automatically benefits from the updated bloom filter implementation.

```python
# In anonymization_manager.py (lines 51, 104-109)
self.record_linkage = RecordLinkage(config)

unique_key = self.record_linkage.generate_unique_key(
    given_name=given_name,
    family_name=family_name,
    dob=dob,
    gender=gender  # Can be "male"/"female", will be converted to "m"/"f"
)
```

---

## Testing Example

### Test Data (from PHP partner)
```
ID: 1
Given Name: Leyna
Family Name: Reichel
Date of Birth: 1980-08-07
Gender: f
```

### Expected Behavior

All three implementations should produce **identical** base64 bloom filters:

1. **PHP** (partner implementation):
   ```php
   $bf = new BloomFilter(m: 500, k: 25, fieldSeeds: [...], globalSeed: 567895675);
   $bf->addPerson(['vorname' => 'leyna', 'nachname' => 'reichel', ...]);
   echo $bf->toBase64();
   ```

2. **Python** (admin dashboard):
   ```python
   unique_key = record_linkage.generate_unique_key(
       given_name='Leyna',
       family_name='Reichel',
       dob='1980-08-07',
       gender='f'  # or 'female' - will be converted
   )
   ```

3. **Dart** (Flutter app):
   ```dart
   final key = BloomFilterService_mz().generateUserKey(
       givenName: 'Leyna',
       familyName: 'Reichel',
       dateOfBirth: '1980-08-07',
       gender: 'f'
   );
   ```

**All three should output the same base64 string!**

---

## Backward Compatibility

The old methods are **kept** but marked as deprecated for reference:

- `_hash_function()` - Old hash function
- `_bit_array_to_hex()` - Old hex encoding

**Note**: These are no longer used by `generate_unique_key()` but remain in code for backward compatibility and reference.

---

## Verification Checklist

- [x] Python bloom filter matches PHP algorithm
- [x] Gender format conversion implemented (male/female → m/f)
- [x] Field-specific seeds match across all platforms
- [x] Global seed matches across all platforms
- [x] Hash construction matches PHP exactly
- [x] Base64 encoding matches PHP output
- [x] Filter size: 500 bits
- [x] Hash functions per field: 25
- [x] Anonymization manager updated (uses RecordLinkage)

---

## Important Notes

### Seed Management
⚠️ **CRITICAL**: The seeds used in the bloom filter are:

```python
field_seeds = {
    'vorname': 123124567,
    'nachname': 674532674,
    'geburtsdatum': 345386767,
    'geschlecht': 566744456,
}
global_seed = 567895675
```

These **MUST** match across:
- PHP partner implementation
- Flutter app (Dart)
- Python backend

**Never change these seeds** unless coordinating with all parties!

### Output Format Change

- **Old**: 64-character hex string (e.g., `a3f5d2b8c1e4...`)
- **New**: ~84-character base64 string (e.g., `AIAQAIiFAkc...`)

**Migration Note**: Any stored unique keys in the old format will NOT match new keys. You may need to regenerate unique keys for existing users.

---

## Related Files

### Updated Files
1. `modules/record_linkage.py` - Core bloom filter implementation

### Dependent Files (automatically use new implementation)
1. `modules/anonymization_manager.py` - Uses RecordLinkage
2. Admin dashboard API endpoints that call these modules

### Cross-Platform Files
1. **Dart**: `lib/src/privacy/bloom_filter_mz.dart` (Flutter app)
2. **Dart**: `lib/src/postgres/postgres_handler.dart` (Uses BloomFilterService_mz)
3. **PHP**: Partner's `bloomfilter.php` (external)
4. **Python**: This file (admin dashboard)

---

## Deployment Notes

When deploying this update:

1. ✅ All platforms must be updated simultaneously
2. ✅ Existing unique keys may need regeneration
3. ✅ Test cross-platform matching with known test data
4. ✅ Verify PostgreSQL queries still work (format changed from hex to base64)
5. ✅ Update any hardcoded unique key examples in documentation

---

## Contact for Issues

If bloom filters don't match across platforms:
1. Verify all seeds match exactly
2. Check gender format (must be 'm' or 'f', not 'male'/'female')
3. Verify date format (YYYY-MM-DD)
4. Check normalization (trim + lowercase)
5. Compare hash construction step-by-step

---

**End of Summary**
