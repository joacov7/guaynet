"""Guaynet Seguridad — all security tables

Revision ID: 026
Revises: 025
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade():
    # ── sec_plans ──────────────────────────────────────────────────────────────
    op.create_table(
        "sec_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("default_features", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── sec_properties ─────────────────────────────────────────────────────────
    op.create_table(
        "sec_properties",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("internet_client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("province", sa.String(100), nullable=True),
        sa.Column("property_type", sa.String(20), nullable=False, server_default="home"),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── sec_subscriptions ──────────────────────────────────────────────────────
    op.create_table(
        "sec_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("sec_properties.id"), nullable=False, index=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("sec_plans.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending_install", index=True),
        sa.Column("beat_account_id", sa.String(100), nullable=True, index=True),
        sa.Column("contract_start", sa.Date(), nullable=True),
        sa.Column("contract_end", sa.Date(), nullable=True),
        sa.Column("billing_day", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── sec_features ───────────────────────────────────────────────────────────
    op.create_table(
        "sec_features",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("feature_name", sa.String(50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.UniqueConstraint("subscription_id", "feature_name", name="uq_sec_feature"),
    )

    # ── sec_property_members ───────────────────────────────────────────────────
    op.create_table(
        "sec_property_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("sec_properties.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="family"),
        sa.Column("can_arm", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("can_disarm", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("can_invite", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("can_view_cameras", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notify_on_alarm", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notify_on_entry", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("schedule_restricted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("schedule_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── sec_emergency_contacts ─────────────────────────────────────────────────
    op.create_table(
        "sec_emergency_contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(50), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("relation", sa.String(100), nullable=True),
        sa.Column("priority_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
    )

    # ── sec_devices ────────────────────────────────────────────────────────────
    op.create_table(
        "sec_devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("device_type", sa.String(30), nullable=False, index=True),
        sa.Column("brand", sa.String(100), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("serial_number", sa.String(255), nullable=True),
        sa.Column("firmware_version", sa.String(50), nullable=True),
        sa.Column("install_date", sa.Date(), nullable=True),
        sa.Column("warranty_months", sa.Integer(), nullable=True),
        sa.Column("location_description", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── sec_device_zones ───────────────────────────────────────────────────────
    op.create_table(
        "sec_device_zones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("sec_devices.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("zone_number", sa.Integer(), nullable=False),
        sa.Column("zone_name", sa.String(100), nullable=True),
        sa.Column("zone_type", sa.String(50), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
    )

    # ── sec_events ─────────────────────────────────────────────────────────────
    op.create_table(
        "sec_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("sec_subscriptions.id"), nullable=False, index=True),
        sa.Column("event_type", sa.String(40), nullable=False, index=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("zone_number", sa.Integer(), nullable=True),
        sa.Column("partition", sa.Integer(), nullable=True),
        sa.Column("user_code", sa.String(50), nullable=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="beat"),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default="false", index=True),
        sa.Column("idempotency_key", sa.String(150), nullable=True, unique=True, index=True),
    )

    # ── sec_alerts ─────────────────────────────────────────────────────────────
    op.create_table(
        "sec_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("sec_subscriptions.id"), nullable=False, index=True),
        sa.Column("source_event_id", sa.Integer(), sa.ForeignKey("sec_events.id", ondelete="SET NULL"), nullable=True),
        sa.Column("alert_type", sa.String(30), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="new", index=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("operator_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("operator_notes", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(100), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── sec_alert_deliveries ───────────────────────────────────────────────────
    op.create_table(
        "sec_alert_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alert_id", sa.Integer(), sa.ForeignKey("sec_alerts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )

    # ── sec_alert_confirmations ────────────────────────────────────────────────
    op.create_table(
        "sec_alert_confirmations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alert_id", sa.Integer(), sa.ForeignKey("sec_alerts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("confirmed_by_member_id", sa.Integer(), sa.ForeignKey("sec_property_members.id", ondelete="SET NULL"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("response", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    # ── sec_entry_sessions ─────────────────────────────────────────────────────
    op.create_table(
        "sec_entry_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("sec_subscriptions.id"), nullable=False, index=True),
        sa.Column("activated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active", index=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.String(100), nullable=True),
        sa.Column("location_lat", sa.Float(), nullable=True),
        sa.Column("location_lon", sa.Float(), nullable=True),
    )

    # ── sec_pin_credentials ────────────────────────────────────────────────────
    op.create_table(
        "sec_pin_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("pin_type", sa.String(20), nullable=False),
        sa.Column("pin_hash", sa.String(255), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── sec_safe_words ─────────────────────────────────────────────────────────
    op.create_table(
        "sec_safe_words",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("word_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── sec_contracts ──────────────────────────────────────────────────────────
    op.create_table(
        "sec_contracts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("accepted_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("accepted_at", sa.String(30), nullable=False),
        sa.Column("acceptance_ip", sa.String(45), nullable=True),
        sa.Column("acceptance_user_agent", sa.String(500), nullable=True),
        sa.Column("document_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── sec_vacation_modes ─────────────────────────────────────────────────────
    op.create_table(
        "sec_vacation_modes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── sec_monthly_reports ────────────────────────────────────────────────────
    op.create_table(
        "sec_monthly_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("sec_subscriptions.id"), nullable=False, index=True),
        sa.Column("period", sa.String(7), nullable=False, index=True),  # YYYY-MM
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="generating"),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("alert_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("test_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("visit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.String(500), nullable=True),
    )


def downgrade():
    # Drop in reverse dependency order
    op.drop_table("sec_monthly_reports")
    op.drop_table("sec_vacation_modes")
    op.drop_table("sec_contracts")
    op.drop_table("sec_safe_words")
    op.drop_table("sec_pin_credentials")
    op.drop_table("sec_entry_sessions")
    op.drop_table("sec_alert_confirmations")
    op.drop_table("sec_alert_deliveries")
    op.drop_table("sec_alerts")
    op.drop_table("sec_events")
    op.drop_table("sec_device_zones")
    op.drop_table("sec_devices")
    op.drop_table("sec_emergency_contacts")
    op.drop_table("sec_property_members")
    op.drop_table("sec_features")
    op.drop_table("sec_subscriptions")
    op.drop_table("sec_properties")
    op.drop_table("sec_plans")
