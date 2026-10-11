"""Production HTTP safeguards using one shared database across WSGI workers."""
import hashlib
import time
from flask import request, jsonify
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.middleware.proxy_fix import ProxyFix
from .db import db
from .models.rate_limit import RateLimit
from .errors import ApiError
from .auth import current_identity

def register_runtime(app):
    hops = app.config.get('TRUSTED_PROXY_HOPS', 0)
    if hops:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=0, x_port=0, x_prefix=0)
    @app.before_request
    def rate_limit():
        if not app.config.get('RATE_LIMIT_ENABLED') or request.method not in ('POST','PUT','PATCH','DELETE') or not request.path.startswith('/api/'):
            return
        expensive = request.path in ('/api/requests/normalize','/api/requests/normalize-photo')
        identity = current_identity()
        # Unauthenticated writes use a separate IP budget; no token is stored.
        subject = 'user:' + identity.subject if identity else 'ip:' + (request.remote_addr or 'unknown')
        scope = 'normalize' if expensive else 'write'
        limit = app.config['NORMALIZE_RATE_PER_MINUTE'] if expensive else app.config['WRITE_RATE_PER_MINUTE']
        key = hashlib.sha256((scope+':'+subject).encode()).hexdigest()
        window = int(time.time())//60
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        dialect = db.engine.dialect.name
        if dialect not in ('postgresql','sqlite'):
            raise ApiError(503,'service_unavailable','Please try again shortly')
        insert = pg_insert if dialect == 'postgresql' else sqlite_insert
        stmt = insert(RateLimit).values(key=key,window=window,count=1).on_conflict_do_update(
            index_elements=['key','window'],set_={'count':RateLimit.count+1},where=RateLimit.count < limit).returning(RateLimit.count)
        try:
            # Independent transaction: quota cannot commit an exchange mutation.
            with db.engine.begin() as connection:
                accepted = connection.execute(stmt).scalar()
        except SQLAlchemyError:
            app.logger.warning('Rate limit database unavailable')
            raise ApiError(503,'service_unavailable','Please try again shortly') from None
        if accepted is None:
            response=jsonify(error={'code':'rate_limited','message':'Too many requests; try again shortly','fields':{}})
            response.status_code=429
            response.headers['Retry-After']=str(60-int(time.time())%60)
            return response
    @app.after_request
    def headers(response):
        response.headers.setdefault('X-Content-Type-Options','nosniff')
        response.headers.setdefault('Referrer-Policy','strict-origin-when-cross-origin')
        if app.config['APP_ENV']=='production':
            response.headers.setdefault('Cache-Control','no-store')
            if request.is_secure:
                response.headers['Strict-Transport-Security']='max-age=31536000'
        return response
