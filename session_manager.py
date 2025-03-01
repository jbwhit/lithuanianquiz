"""Database-backed session management for Lithuanian language learning app."""
import json
import random
import time
import uuid

from starlette.responses import RedirectResponse

from fasthtml.common import cookie
from fastlite import database

# Initialize the database connection for sessions
sessions_db = database("sessions.db")

# Create sessions table if it doesn't exist
if "sessions" not in sessions_db.t:
    sessions_db.t.sessions.create(
        id=str,
        data=str,  # JSON serialized session data
        last_access=float,
        pk="id"
    )

def get_session(request):
    """Get session data from database using cookie ID."""
    session_id = request.cookies.get("lithuanian_session_id")

    # If we have a valid session ID, retrieve it
    if session_id:
        try:
            session_row = sessions_db.t.sessions[session_id]
            # Deserialize the session data
            # session_data = json.loads(session_row.data)
            session_data = json.loads(session_row["data"])


            # Update last access time
            sessions_db.t.sessions.update(
                {"last_access": time.time()},
                session_id
            )

            return session_data, session_id
        except Exception as e:
            print(f"Error retrieving session {session_id}: {e}")
            # If session not found or invalid, continue to create new
            pass

    # Create a new session
    session_id = str(uuid.uuid4())
    empty_session = {}
    sessions_db.t.sessions.insert({
        "id": session_id,
        "data": json.dumps(empty_session),
        "last_access": time.time()
    })

    return empty_session, session_id

def save_session(session_id, session_data):
    """Save session data to database."""
    try:
        # Serialize the session data
        serialized_data = json.dumps(session_data)

        # Update the session in the database
        sessions_db.t.sessions.update({
            "data": serialized_data,
            "last_access": time.time()
        }, session_id)

        return True
    except Exception as e:
        print(f"Error saving session: {e}")
        return False

def cleanup_old_sessions(max_age=86400):
    """Remove sessions older than max_age seconds."""
    cutoff_time = time.time() - max_age
    try:
        # Find old sessions
        old_sessions = list(sessions_db.t.sessions(where=f"last_access < {cutoff_time}"))

        # Delete them
        for session in old_sessions:
            sessions_db.t.sessions.delete(session.id)

        return len(old_sessions)
    except Exception as e:
        print(f"Error cleaning up sessions: {e}")
        return 0

def maybe_cleanup_sessions(probability=0.01, max_age=86400):
    """Run cleanup with a certain probability."""
    if random.random() < probability:
        num_cleaned = cleanup_old_sessions(max_age)
        if num_cleaned > 0:
            print(f"Cleaned up {num_cleaned} old sessions")

def add_session_cookie(response, session_id):
    """Add session cookie to response."""
    if isinstance(response, RedirectResponse):
        response.set_cookie("lithuanian_session_id", session_id, max_age=86400)
        return response
    else:
        # For FastHTML responses that don't directly accept cookies
        return response, cookie("lithuanian_session_id", session_id, max_age=86400)
