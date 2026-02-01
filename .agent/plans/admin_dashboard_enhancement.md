# Admin Dashboard & Registration Enhancement Plan

## Goal
Enhance the admin dashboard to display Email, Phone, and Name fields, and update the registration flow to collect these fields. Ensure the database is updated to support these new fields.

## Current Status
- [x] **Frontend (UI)**:
    - Added Email field to Registration Dialog (`ui/login_ui_modern.py`).
    - Added Name, Email, Phone, Password columns to Admin User Table (`ui/admin_dashboard.py`).
    - Refined error messages and layout.
- [x] **Backend (API)**:
    - Updated `RegistrationRequest` schema and models.
    - Updated `User` model.
    - Updated `admin` and `registration` routers to handle new fields.
    - Fixed IP utility duplication (`app/utils/ip_utils.py`).
    - Renamed `app/config.py` to `app/configuration.py` to avoid conflicts.
- [ ] **Database**:
    - Migration script `backend/run_db_update.py` created but failed to connect (missing proxy).
    - **Action**: Need to run migration on the server or via a temporary API endpoint.

## Immediate Fixes
- [x] **Critical Bug**: Fixed `SyntaxError` in `ui/login_ui_modern.py` caused by git conflict markers.
- [x] **Configuration**: Fixed import errors in backend by renaming config module.

## Next Steps
1. **Verify UI Fix**: User to run the application again to confirm startup.
2. **Database Migration**:
    - Create a temporary migration endpoint in the backend (`/admin/db-migrate`).
    - Deploy backend to Cloud Run.
    - Trigger migration via API.
3. **Testing**:
    - Test Registration with new Email field.
    - Verify Admin Dashboard User Table populates correctly.
