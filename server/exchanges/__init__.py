"""Person 4: exchange workflow (messages, offers, acceptance, handoff, return,
review, dispute). Owned by Person 4 (branch p4-exchanges).

Person 1 created ``routes.py`` with labeled fixture responses for reads and
501 responses for writes so the UI can be wired up. Replace them in place.
Helpers to build on:
    server.auth.require_verified_user / current_profile
    server.reservation.reserve_listing / release_listing / mark_listing_sold
    server.storage.get_storage / authorize_private_read
    server.validation.*
"""
