"""Initial schema — all core tables.
Revision ID: 0001
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users",
        sa.Column("id",           postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email",        sa.String(255), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("is_active",    sa.Boolean(), server_default="true", nullable=False),
        sa.Column("plan",         sa.String(50),  server_default="starter", nullable=False),
        sa.Column("created_at",   sa.DateTime(),  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at",   sa.DateTime(),  nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table("api_keys",
        sa.Column("id",           postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id",      postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key_hash",     sa.String(255), nullable=False),
        sa.Column("name",         sa.String(100), nullable=True),
        sa.Column("is_active",    sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at",   sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at",   sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table("verifications",
        sa.Column("id",                  postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id",          sa.String(255), nullable=False),
        sa.Column("user_id",             postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("api_key_id",          postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("human_trust_score",   sa.Integer(), nullable=True),
        sa.Column("combined_score",      sa.String(10), nullable=True),
        sa.Column("behavioral_score",    sa.String(10), nullable=True),
        sa.Column("text_score",          sa.String(10), nullable=True),
        sa.Column("liveness_score",      sa.String(10), nullable=True),
        sa.Column("deepfake_probability",sa.String(10), nullable=True),
        sa.Column("clone_probability",   sa.String(10), nullable=True),
        sa.Column("verdict",             sa.String(50), nullable=True),
        sa.Column("confidence",          sa.String(20), nullable=True),
        sa.Column("flags",               postgresql.JSON(), nullable=True),
        sa.Column("signals_analyzed",    postgresql.JSON(), nullable=True),
        sa.Column("action_type",         sa.String(100), nullable=True),
        sa.Column("platform_user_id",    sa.String(255), nullable=True),
        sa.Column("ip_address",          sa.String(45),  nullable=True),
        sa.Column("user_agent",          sa.Text(), nullable=True),
        sa.Column("status",              sa.String(20), server_default="pending", nullable=False),
        sa.Column("processing_time_ms",  sa.Integer(), nullable=True),
        sa.Column("created_at",          sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at",        sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_verifications_session_id",  "verifications", ["session_id"])
    op.create_index("ix_verifications_created_at",  "verifications", ["created_at"])
    op.create_index("ix_verifications_platform_uid","verifications", ["platform_user_id"])

    op.create_table("scores",
        sa.Column("id",                 postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id",            postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform_user_id",   sa.String(255), nullable=False),
        sa.Column("current_score",      sa.Float(), server_default="50.0", nullable=False),
        sa.Column("verification_count", sa.Integer(), server_default="0"),
        sa.Column("last_verified_at",   sa.DateTime(), nullable=True),
        sa.Column("created_at",         sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at",         sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scores_platform_user_id", "scores", ["platform_user_id"])

    op.create_table("webhook_endpoints",
        sa.Column("id",         postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id",    postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url",        sa.String(2048), nullable=False),
        sa.Column("secret",     sa.String(255), nullable=True),
        sa.Column("is_active",  sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table("webhook_deliveries",
        sa.Column("id",              postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("endpoint_id",     postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verification_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status",          sa.String(20), server_default="pending"),
        sa.Column("response_code",   sa.Integer(), nullable=True),
        sa.Column("attempt_count",   sa.Integer(), server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("created_at",      sa.DateTime(), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["endpoint_id"],     ["webhook_endpoints.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verification_id"], ["verifications.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("webhook_deliveries")
    op.drop_table("webhook_endpoints")
    op.drop_table("scores")
    op.drop_table("verifications")
    op.drop_table("api_keys")
    op.drop_table("users")
