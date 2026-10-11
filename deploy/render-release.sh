#!/bin/sh
# Run once as the Render pre-deploy command, only after migration approval.
# A failed migration/readiness check prevents the new build from serving traffic.
set -eu
flask --app server.app db upgrade c708communitymerge
flask --app server.app backend-diagnostics --require-ready
