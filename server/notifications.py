"""Generate events in the same flush as successful domain mutations.

History inspection means retried accept/confirm actions generate no new event.
The unique recipient/event constraint also guards duplicate writes. Rollbacks
roll back notifications with the exchange operation.
"""
from flask import has_request_context
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session
from .auth import current_profile
from .db import new_id
from .models import Exchange, OfferRevision, Message, Evidence, ExchangeLocation
from .models.notification import Notification

@event.listens_for(Session, 'before_flush')
def exchange_notifications(session, flush_context, instances):
    if not has_request_context():
        return
    candidates = [obj for obj in list(session.new) + list(session.dirty) if isinstance(obj,(Exchange,OfferRevision,Message,Evidence))]
    if not candidates:
        return
    actor = current_profile()
    if actor is None:
        return
    def emit(exchange, kind, key):
        for recipient in exchange.participant_ids - {actor.id}:
            if any(isinstance(n, Notification) and n.recipient_id == recipient and n.event_key == key for n in session.new):
                continue
            with session.no_autoflush:
                exists = session.query(Notification.id).filter_by(recipient_id=recipient, event_key=key).first()
            if not exists:
                session.add(Notification(recipient_id=recipient,exchange=exchange,exchange_id=exchange.id,kind=kind,event_key=key))
    for obj in candidates:
        if not isinstance(obj, (Exchange, OfferRevision, Message, Evidence)):
            continue
        state = inspect(obj)
        if obj.id is None:
            obj.id = new_id()
        if isinstance(obj, Exchange):
            if obj in session.new:
                emit(obj, 'exchange_created', 'exchange:' + obj.id)
            elif state.attrs.status.history.has_changes():
                if obj.status in ("completed","cancelled","disputed"):
                    session.query(ExchangeLocation).filter_by(exchange_id=obj.id).delete(synchronize_session="fetch")
                emit(obj, obj.status, f'status:{obj.id}:{obj.status}')
            for field in ('owner_service_confirmed_at','requester_service_confirmed_at'):
                if getattr(obj,field) and state.attrs[field].history.has_changes():
                    emit(obj,'completion_confirmation',f'complete:{obj.id}:{field}')
        else:
            with session.no_autoflush:
                exchange = getattr(obj, 'exchange', None) or session.get(Exchange, obj.exchange_id)
            if exchange is None:
                exchange = next((x for x in session.new if isinstance(x,Exchange) and x.id == obj.exchange_id), None)
            if exchange is None:
                continue
            if isinstance(obj, Message) and obj in session.new:
                emit(exchange, 'message', 'message:' + obj.id)
            elif isinstance(obj, OfferRevision):
                if obj in session.new:
                    emit(exchange, 'offer', 'offer:' + obj.id)
                for field in ('owner_accepted_at','requester_accepted_at'):
                    if getattr(obj,field) and state.attrs[field].history.has_changes():
                        emit(exchange, 'offer_accepted', f'accept:{obj.id}:{field}')
            elif isinstance(obj,Evidence):
                if obj in session.new:
                    emit(exchange,'confirmation_required','evidence:' + obj.id)
                elif state.attrs.acknowledged_by.history.has_changes():
                    for participant in (obj.acknowledged_by or {}):
                        emit(exchange,'condition_confirmation',f'evidence-confirm:{obj.id}:{participant}')
