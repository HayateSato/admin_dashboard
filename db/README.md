# Database Files

This folder contains PostgreSQL database schema and data files.

## Files

| File | Description |
|------|-------------|
| `schema.sql` | Database schema definition (tables, sequences, constraints) |
| `dump_clean.sql` | Initial data for the database |
| `install_schema.bat` | Windows batch script for manual schema installation |

## When to Use `install_schema.bat`

This script is for **manual, local PostgreSQL installations only**.

### Use this script when:
- Running PostgreSQL directly on your machine (not in Docker)
- Setting up a development environment without Docker
- Need to reset/reinstall the schema on an existing local database

### Do NOT use this script when:
- Using Docker Compose (`docker-compose up`) - schema is automatically loaded via init scripts
- Database is already initialized with the schema

## How to Run

1. Open a terminal in the `db` folder
2. Ensure PostgreSQL is running and the `privacy_umbrella` database exists
3. Run:
   ```
   install_schema.bat
   ```

## Docker Usage

When using Docker Compose, these files are automatically mounted and executed in order:
1. `schema.sql` → `/docker-entrypoint-initdb.d/01_schema.sql`
2. `dump_clean.sql` → `/docker-entrypoint-initdb.d/02_data.sql`

The PostgreSQL container runs these scripts automatically on first initialization.
