# Token blacklist module removed.
# Session revocation is handled via SessionModel.is_active in the database.
# See: dependencies.py get_current_user_id() and auth_service.py check_session()
