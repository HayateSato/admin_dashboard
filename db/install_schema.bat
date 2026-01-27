@echo off
REM Install Privacy-Compliant Database Schema
REM This script installs the new tables into the existing 'pu' database

echo ========================================
echo Privacy Umbrella - Schema Installation
echo ========================================
echo.
echo This will create the following tables in the 'privacy_umbrella' database:
echo.
echo ACTIVE TABLES (will be created):
echo - users (privacy-compliant, NO PII)
echo - admin_users
echo - privacy_policies
echo.
echo COMMENTED OUT (not created):
echo - sessions
echo - audit_logs
echo - fl_rounds
echo - anonymization_jobs
echo.
echo NOTE: The existing 'user_sessions' table will NOT be modified.
echo.

set /p CONTINUE="Continue? (Y/N): "
if /i not "%CONTINUE%"=="Y" (
    echo Installation cancelled.
    exit /b
)

echo.
echo Installing schema...
echo.

REM Run the schema file
REM Note: Update database name if different from 'privacy_umbrella'
psql -U postgres -d privacy_umbrella -f schema.sql

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo Schema installed successfully!
    echo ========================================
    echo.
    echo Next steps:
    echo 1. Update .env file with database credentials
    echo 2. Start admin dashboard: python app.py
    echo 3. Test record linkage functionality
    echo.
    echo Default admin login:
    echo   Username: admin
    echo   Password: admin123 ^(CHANGE THIS!^)
    echo.
) else (
    echo.
    echo ========================================
    echo ERROR: Schema installation failed!
    echo ========================================
    echo.
    echo Please check:
    echo 1. PostgreSQL is running
    echo 2. Database 'privacy_umbrella' exists
    echo 3. User 'postgres' has correct password
    echo.
    echo You can install manually:
    echo   psql -U postgres -d privacy_umbrella -f schema.sql
    echo.
)

pause
