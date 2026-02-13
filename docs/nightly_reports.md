# Nightly Observation Reports

## Overview

POCS now automatically generates nightly observation reports that provide a comprehensive summary of each observing night. These reports are generated at the end of the night during the housekeeping state.

## Report Contents

Each nightly report includes:

1. **Observations Summary**
   - Total number of observation sequences
   - Number of unique fields observed
   - Details for each field including:
     - Field name
     - Start time
     - Number of exposures taken vs. planned

2. **Safety Summary**
   - Status of all safety checks:
     - AC Power Connected
     - Dark Sky
     - Weather Safe
     - Root Disk Space
     - Image Disk Space
   - Reasons for non-observation (if any):
     - Unsafe weather conditions
     - Not dark enough for observations
     - AC power issues
     - Insufficient disk space

## Configuration

Reports are saved to a configurable directory. By default, they are saved to `~/reports`, but this can be customized in your POCS configuration:

```yaml
directories:
  reports: /path/to/your/reports/directory
```

## Report Files

Reports are saved with the naming convention:
```
nightly_report_YYYYMMDD.txt
```

For example: `nightly_report_20260213.txt`

## Sample Report

```
================================================================================
PANOPTES Nightly Observation Report - 2026-02-13
================================================================================

OBSERVATIONS SUMMARY
--------------------------------------------------------------------------------
Total observation sequences: 2
Unique fields observed: 2

Observations by field:
  - M42OrionNebula: 1 sequence(s)
    * Started: 2026-02-13T01:30:00, Exposures: 0/30
  - M31Andromeda: 1 sequence(s)
    * Started: 2026-02-13T03:15:00, Exposures: 0/40

SAFETY SUMMARY
--------------------------------------------------------------------------------
Most recent safety check:
  AC Power Connected...................... ✓ PASS
  Dark Sky................................ ✓ PASS
  Weather Safe............................ ✗ FAIL
  Root Disk Space......................... ✓ PASS
  Image Disk Space........................ ✓ PASS

WARNING: Some safety checks failed.
Reasons for non-observation:
  - Unsafe weather conditions

================================================================================
End of Report
================================================================================
```

## Implementation Details

The nightly report feature is implemented in:
- `src/panoptes/pocs/utils/report.py` - Core report generation logic
- `src/panoptes/pocs/state/states/default/housekeeping.py` - Integration with state machine

The report generator queries the POCS database for:
- Observed list from the scheduler
- Most recent safety check data

Reports are generated automatically during the housekeeping state at the end of each night, before the observed list is reset.

## Testing

Comprehensive tests are included in:
- `tests/utils/test_report.py` - Unit tests for report generation
- `tests/test_housekeeping_state.py` - Integration tests

Run tests with:
```bash
pytest tests/utils/test_report.py tests/test_housekeeping_state.py -v
```
