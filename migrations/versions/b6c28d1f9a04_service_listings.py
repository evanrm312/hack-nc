"""Add service listing, request, and exchange fields.

Revision ID: b6c28d1f9a04
Revises: a44534641a4c
"""

from alembic import op
import sqlalchemy as sa


revision = "b6c28d1f9a04"
down_revision = "a44534641a4c"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("listings") as batch_op:
        batch_op.add_column(sa.Column("service_price_cents", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("service_duration_minutes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("service_available_windows", sa.JSON(), nullable=True))
    with op.batch_alter_table("need_requests") as batch_op:
        batch_op.add_column(sa.Column("service_duration_minutes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("service_time_windows", sa.JSON(), nullable=True))
    with op.batch_alter_table("exchanges") as batch_op:
        batch_op.add_column(sa.Column("owner_service_confirmed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("requester_service_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("offer_revisions") as batch_op:
        batch_op.add_column(sa.Column("service_price_cents", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("service_duration_minutes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("service_scheduled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table("offer_revisions") as batch_op:
        batch_op.drop_column("service_scheduled_at")
        batch_op.drop_column("service_duration_minutes")
        batch_op.drop_column("service_price_cents")
    with op.batch_alter_table("exchanges") as batch_op:
        batch_op.drop_column("requester_service_confirmed_at")
        batch_op.drop_column("owner_service_confirmed_at")
    with op.batch_alter_table("need_requests") as batch_op:
        batch_op.drop_column("service_time_windows")
        batch_op.drop_column("service_duration_minutes")
    with op.batch_alter_table("listings") as batch_op:
        batch_op.drop_column("service_available_windows")
        batch_op.drop_column("service_duration_minutes")
        batch_op.drop_column("service_price_cents")
