"""create profile and listing

Revision ID: 984004487979
Revises: 
Create Date: 2026-10-10 13:21:01.140317

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '984004487979'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "profile",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("confirmed_email_domain", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_profile")),
    )
    op.create_table(
        "listing",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("specifications", sa.JSON(), nullable=True),
        sa.Column("condition", sa.Text(), nullable=True),
        sa.Column("accessories", sa.JSON(), nullable=True),
        sa.Column("mode", sa.String(length=10), nullable=False),
        sa.Column("sale_price_cents", sa.Integer(), nullable=True),
        sa.Column("rental_fee_cents", sa.Integer(), nullable=True),
        sa.Column("proposed_item_value_cents", sa.Integer(), nullable=True),
        sa.Column("collateral_percent", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("public_photo_path", sa.String(length=500), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("mode IN ('sale', 'borrow', 'both')", name=op.f("ck_listing_valid_mode")),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'reserved', 'sold', 'archived')",
            name=op.f("ck_listing_valid_status"),
        ),
        sa.CheckConstraint("sale_price_cents >= 0", name=op.f("ck_listing_sale_price_nonnegative")),
        sa.CheckConstraint("rental_fee_cents >= 0", name=op.f("ck_listing_rental_fee_nonnegative")),
        sa.CheckConstraint("proposed_item_value_cents >= 0", name=op.f("ck_listing_item_value_nonnegative")),
        sa.CheckConstraint(
            "collateral_percent BETWEEN 0 AND 100",
            name=op.f("ck_listing_collateral_percent_range"),
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["profile.id"], name=op.f("fk_listing_owner_id_profile")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_listing")),
    )
    op.create_index(op.f("ix_listing_owner_id"), "listing", ["owner_id"])


def downgrade():
    op.drop_index(op.f("ix_listing_owner_id"), table_name="listing")
    op.drop_table("listing")
    op.drop_table("profile")
