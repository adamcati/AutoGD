import posthog
from flask_login import current_user
from flask import request

def track_event(event_name, properties=None, distinct_id=None):
    # Use provided distinct_id or current_user.id if available
    user_id = distinct_id or (str(current_user.id) if current_user.is_authenticated else None)
    
    posthog.capture(
        distinct_id=user_id or 'anonymous',
        event=event_name,
        properties=properties or {}
    )

def track_extraction_error(user_id, error_type, error_message):
    track_event(
        'extraction_error',
        {
            'user_id': user_id,
            'error_type': error_type,
            'error_message': error_message
        },
        distinct_id=user_id
    )

def track_subscription_event(user_id, event_type):
    track_event(
        event_type,
        {'user_id': user_id},
        distinct_id=user_id
    )

def track_text_correction(user_id, original_text, corrected_text):
    track_event(
        'text_correction',
        {
            'user_id': user_id,
            'original_text': original_text,
            'corrected_text': corrected_text
        },
        distinct_id=user_id
    )

def track_auth_event(user_id, event_type, success=True, error_message=None):
    track_event(
        'auth_event',
        {
            'user_id': user_id,
            'event_type': event_type,  # login, register, verify_email, reset_password
            'success': success,
            'error_message': error_message
        },
        distinct_id=user_id
    )

def track_session_event(user_id, event_type, duration=None):
    track_event(
        'session_event',
        {
            'user_id': user_id,
            'event_type': event_type,  # start, end, page_view
            'duration': duration,
            'path': request.path if 'request' in globals() else None
        },
        distinct_id=user_id
    )

def track_feature_usage(user_id, feature_name, action_type):
    track_event(
        'feature_usage',
        {
            'user_id': user_id,
            'feature': feature_name,
            'action': action_type
        },
        distinct_id=user_id
    )
