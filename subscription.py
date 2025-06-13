from fastapi import HTTPException
from firebase import db  # your Firestore client
from datetime import datetime, timedelta, timezone


async def check_and_update_access(email: str):
    """
    Checks if the user with the given email has access based on:
    - Active subscription (subscription_end in the future)
    - One-time free use (freeUsed = False)

    Updates freeUsed to True if using the free use.

    Raises HTTPException 403 if no access.
    """
    user_query = db.collection("users").where("email", "==", email).limit(1)
    docs = user_query.stream()
    user_doc = next(docs, None)

    now = datetime.now(timezone.utc)

    if not user_doc:
        # New user: create document and grant free use immediately (freeUsed = True)
        new_doc_ref = db.collection("users").document()
        new_doc_ref.set({
            "email": email,
            "freeUsed": True,
            "subscription_end": None,
        })
        return  # Access granted

    user_data = user_doc.to_dict()
    doc_ref = db.collection("users").document(user_doc.id)

    # Check subscription end date
    subscription_end = user_data.get("subscription_end")

    if subscription_end:
        # Firestore timestamps may come as special objects or dicts
        subscription_end_dt = None
        if hasattr(subscription_end, "timestamp"):
            subscription_end_dt = subscription_end.to_datetime()
        elif isinstance(subscription_end, dict) and "_seconds" in subscription_end:
            subscription_end_dt = datetime.fromtimestamp(subscription_end["_seconds"], tz=timezone.utc)
        elif isinstance(subscription_end, str):
            subscription_end_dt = datetime.fromisoformat(subscription_end)

        if subscription_end_dt and subscription_end_dt > now:
            # Active subscription, access allowed
            return

    # No active subscription, check free use
    if not user_data.get("freeUsed", False):
        # Allow free use once, mark as used
        doc_ref.update({"freeUsed": True})
        return

    # No access granted
    raise HTTPException(status_code=403, detail="Free access already used or subscription expired")


def extend_subscription(email: str, days: int = 30):
    """
    Extends (or creates) a subscription for the user by `days`.
    If subscription is active, adds days.
    Otherwise, sets subscription_end to now + days.
    Creates user if doesn't exist.
    """
    user_query = db.collection("users").where("email", "==", email).limit(1)
    docs = user_query.stream()
    user_doc = next(docs, None)

    now = datetime.now(timezone.utc)

    if user_doc:
        user_data = user_doc.to_dict()
        doc_ref = db.collection("users").document(user_doc.id)

        subscription_end = user_data.get("subscription_end")
        subscription_end_dt = None

        if subscription_end:
            if hasattr(subscription_end, "timestamp"):
                subscription_end_dt = subscription_end.to_datetime()
            elif isinstance(subscription_end, dict) and "_seconds" in subscription_end:
                subscription_end_dt = datetime.fromtimestamp(subscription_end["_seconds"], tz=timezone.utc)
            elif isinstance(subscription_end, str):
                subscription_end_dt = datetime.fromisoformat(subscription_end)

        if subscription_end_dt and subscription_end_dt > now:
            new_end = subscription_end_dt + timedelta(days=days)
        else:
            new_end = now + timedelta(days=days)

        doc_ref.update({"subscription_end": new_end})
    else:
        # Create new user doc with subscription_end
        new_doc_ref = db.collection("users").document()
        new_doc_ref.set({
            "email": email,
            "freeUsed": True,  # Since we give subscription, mark free use consumed
            "subscription_end": now + timedelta(days=days),
        })
