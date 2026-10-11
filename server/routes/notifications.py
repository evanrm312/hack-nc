from flask import Blueprint, jsonify
from ..auth import current_profile, require_verified_user
from ..db import db, utcnow
from ..errors import not_found
from ..models.notification import Notification
bp = Blueprint('notifications', __name__, url_prefix='/api/notifications')

@bp.after_request
def private(response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

@bp.get('')
@require_verified_user
def notifications():
    query = db.select(Notification).where(Notification.recipient_id == current_profile().id)
    rows = db.session.scalars(query.order_by(Notification.created_at.desc(),Notification.id.desc()).limit(100)).all()
    unread = db.session.scalar(db.select(db.func.count()).select_from(Notification).where(
        Notification.recipient_id == current_profile().id,Notification.read_at.is_(None)))
    return jsonify(notifications=[n.to_dict() for n in rows],unread_count=unread)

@bp.post('/read-all')
@require_verified_user
def read_all():
    db.session.execute(db.update(Notification).where(Notification.recipient_id == current_profile().id,
        Notification.read_at.is_(None)).values(read_at=utcnow()))
    db.session.commit()
    return jsonify(ok=True)

@bp.post('/<notification_id>/read')
@require_verified_user
def read(notification_id):
    row = db.session.get(Notification,notification_id)
    if row is None or row.recipient_id != current_profile().id:
        raise not_found('notification')
    if row.read_at is None:
        row.read_at=utcnow()
        db.session.commit()
    return jsonify(notification=row.to_dict())
