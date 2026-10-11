"""Docker runtime. Proxy trust must be explicitly scoped to the reverse proxy."""
import os
bind = '0.0.0.0:' + os.environ.get('PORT','8080')
workers = int(os.environ.get('WEB_WORKERS','2'))
worker_class = 'gthread'
threads = 2
timeout = 75  # exceeds the existing 32-second Gemini deadline and storage/auth timeouts
graceful_timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
accesslog = '-'  # path only: no query strings, headers, bodies or tokens
access_log_format = '%(s)s %(m)s %(U)s %(L)s'
errorlog = '-'
forwarded_allow_ips = os.environ.get('FORWARDED_ALLOW_IPS','127.0.0.1')
preload_app = False
control_socket_disable = True  # read-only Docker filesystem; no runtime control socket
worker_tmp_dir = '/tmp'
