"""Fictional demo communities only; called inside the protected demo transaction."""
from uuid import NAMESPACE_URL, uuid5
from werkzeug.security import generate_password_hash
from .db import db
from .models import Club, ClubMembership, Profile

# Fictional team demo codes, also documented in docs/community-clubs.md.
# These are not production secrets or real UNC organization access codes.
DEMO_CLUBS = (
    ('demo-study-circle', 'Study Circle (fictional DEMO club)', 'DEMO-STUDY-2026',
     {'alice@unc.edu': 'member', 'bob@unc.edu': 'member', 'carol@unc.edu': 'manager'}),
    ('demo-sharing-circle', 'Sharing Circle (fictional DEMO club)', 'DEMO-SHARE-2026',
     {'alice@unc.edu': 'manager', 'carol@unc.edu': 'member'}),
)


def seed_demo_clubs():
    from .seed import sandbox_subject
    out = []
    for slug, name, code, roles in DEMO_CLUBS:
        club = db.session.scalar(db.select(Club).where(Club.slug == slug))
        if club is None:
            club = Club(id=uuid5(NAMESPACE_URL, 'campus-current:demo-club:' + slug).hex,
                        slug=slug, name=name, code_hash=generate_password_hash(code), is_demo=True)
            db.session.add(club); db.session.flush()
            out.append('fictional demo club created: ' + slug)
        elif not club.is_demo:
            raise ValueError('Demo club slug collision')
        for email, role in roles.items():
            profile = db.session.scalar(db.select(Profile).where(Profile.auth_subject == sandbox_subject(email)))
            if profile is None:
                continue
            if not profile.is_demo or profile.verification_source != 'sandbox':
                raise ValueError('Demo club profile collision')
            existing = db.session.scalar(db.select(ClubMembership).where(
                ClubMembership.club_id == club.id, ClubMembership.profile_id == profile.id))
            if existing is None:
                db.session.add(ClubMembership(club_id=club.id, profile_id=profile.id, role=role))
                out.append('fictional demo membership created')
    return out
