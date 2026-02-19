# Field Configuration Files

This directory contains YAML files that define observing targets (fields) for the POCS scheduler.

## Field File Format

Each field configuration file is a YAML list where each item defines:
- A **field**: the target's name and position
- An **observation**: observation parameters for that field

### Basic Example

```yaml
- field:
    name: "M42"
    position: "05h35m17.2992s -05d23m27.996s"
  observation:
    priority: 100
    exptime: 30
    min_nexp: 10
    exp_set_size: 5
```

## Field Parameters

### `field` section

- **name** (required): Human-readable name for the target
- **position** (required): Sky coordinates in one of these formats:
  - HMS/DMS: `"05h35m17.2992s -05d23m27.996s"`
  - Degrees: `"83.82deg -5.39deg"`
  - Mixed: `"05h35m17s -5.39deg"`

### `observation` section

- **priority** (optional, default: 100): Higher priority targets are observed first
- **exptime** (optional, default: 120): Exposure time in seconds
- **min_nexp** (optional, default: 60): Minimum number of exposures to take
- **exp_set_size** (optional, default: 10): Number of exposures per set
- **filter_name** (optional): Filter to use for this observation
- **tags** (optional): List of string labels for categorizing observations

## Tags Feature

Tags allow you to label observations with arbitrary strings for metadata searching and filtering. Tags are stored in observation metadata and written to FITS headers.

### Example with Tags

```yaml
- field:
    name: "KIC 8462852"
    position: "20h06m15.4536s +44d27m24.75s"
  observation:
    priority: 100
    exptime: 60
    tags:
      - exoplanet
      - tabby_star
      - variable
```

Tags can be used to:
- Categorize observations by science goal (e.g., "exoplanet", "variable_star")
- Mark special observation types (e.g., "defocus_test", "commissioning")
- Group related targets (e.g., "tess_sector_1", "galactic_plane")
- Aid in data analysis and archiving

## Available Files

- **simple.yaml**: Basic example targets for testing and demonstration
- **simulator.yaml**: Single target for simulator testing
- **tess_sectors_north.yaml**: TESS northern hemisphere sectors
- **tess_sectors_south.yaml**: TESS southern hemisphere sectors

## Using Field Files

Specify which field file to use in your main POCS configuration:

```yaml
scheduler:
  fields_file: simple
```

The `.yaml` extension is automatically added.
