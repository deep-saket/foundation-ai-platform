"""Initial platform schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "models",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("family", sa.String(length=128), nullable=False),
        sa.Column("engine", sa.String(length=128), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("vllm_eagle_head", sa.String(length=512), nullable=True),
        sa.Column("memory_requirement_gb", sa.Integer(), nullable=False),
        sa.Column("ownership", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    op.create_table(
        "deployments",
        sa.Column("deployment_id", sa.String(length=64), primary_key=True),
        sa.Column("model_id", sa.String(length=64), sa.ForeignKey("models.id"), nullable=False),
        sa.Column("endpoint", sa.String(length=512), nullable=False),
        sa.Column("engine", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_used", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_deployments_model_id", "deployments", ["model_id"], unique=False)
    op.create_table(
        "lifecycle_states",
        sa.Column("deployment_id", sa.String(length=64), sa.ForeignKey("deployments.deployment_id"), primary_key=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("last_transition", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_duration_seconds", sa.Integer(), nullable=False),
    )
    op.create_table(
        "telemetry",
        sa.Column("request_id", sa.String(length=64), primary_key=True),
        sa.Column("deployment_id", sa.String(length=64), sa.ForeignKey("deployments.deployment_id"), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("e2e_latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("ttft_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("tpot_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("itl_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("speculative_decoding", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("error", sa.String(length=1024), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("telemetry")
    op.drop_table("lifecycle_states")
    op.drop_index("ix_deployments_model_id", table_name="deployments")
    op.drop_table("deployments")
    op.drop_table("models")
