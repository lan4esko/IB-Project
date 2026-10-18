from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def now(): return datetime.now(timezone.utc)

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="admin")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Session(Base):
    __tablename__ = "login_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class InformationObject(Base):
    __tablename__ = "information_objects"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    classification: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    location: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="formation", nullable=False)
    openproject_project_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now, nullable=False)

class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    oi_id: Mapped[int] = mapped_column(ForeignKey("information_objects.id", ondelete="RESTRICT"), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    inventory_number: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    device_type: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    model: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    os_name: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    os_version: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    network_segment: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    ip_address: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    hostname: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    domain_name: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    seal_state: Mapped[str] = mapped_column(String(36), default="unknown", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="operational", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now, nullable=False)
    __table_args__ = (Index("ix_assets_oi_id", "oi_id"),Index("ix_assets_serial_number", "serial_number"),Index("ix_assets_inventory_number", "inventory_number"),Index("ix_assets_network_segment", "network_segment"),Index("ix_assets_status", "status"))

class FieldDefinition(Base):
    __tablename__ = "field_definitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    field_type: Mapped[str] = mapped_column(String(20), nullable=False)
    options: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __table_args__ = (UniqueConstraint("entity_type", "scope_entity_id", "name", name="uq_field_entity_scope_name"), Index("ix_field_def_scope", "entity_type", "scope_entity_id"))

class FieldValue(Base):
    __tablename__ = "field_values"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field_id: Mapped[int] = mapped_column(ForeignKey("field_definitions.id", ondelete="RESTRICT"), nullable=False)
    value: Mapped[object] = mapped_column(JSON, nullable=True)
    value_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now, nullable=False)
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", "field_id", name="uq_field_value"),Index("ix_field_values_lookup", "entity_type", "entity_id"),Index("ix_field_values_search", "field_id", "value_text"))

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class FieldAssertionRevision(Base):
    """Immutable version of a concrete built-in or custom field value."""
    __tablename__ = "field_assertion_revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field_key: Mapped[str] = mapped_column(String(80), nullable=False)
    value_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    __table_args__ = (Index("ix_assertion_version_lookup", "entity_type", "entity_id", "field_key", "id"),)

class FieldEvidence(Base):
    __tablename__ = "field_evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field_key: Mapped[str] = mapped_column(String(80), nullable=False)
    value_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    value_revision_id: Mapped[int] = mapped_column(ForeignKey("field_assertion_revisions.id", ondelete="RESTRICT"), nullable=False)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="evidence")
    locator_type: Mapped[str] = mapped_column(String(30), nullable=False)
    locator_value: Mapped[str] = mapped_column(String(150), nullable=False)
    comment: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    __table_args__ = (Index("ix_evidence_field", "entity_type", "entity_id", "field_key"),)

class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)

class FieldValueRevision(Base):
    __tablename__ = "field_value_revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field_id: Mapped[int] = mapped_column(ForeignKey("field_definitions.id", ondelete="RESTRICT"), nullable=False)
    value: Mapped[object] = mapped_column(JSON, nullable=True)
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    __table_args__ = (Index("ix_field_revisions_lookup", "entity_type", "entity_id", "field_id"),)


class ConfigurationBaseline(Base):
    """Immutable snapshot of the composition of one OI. Approval is separate."""
    __tablename__ = "configuration_baselines"
    id: Mapped[int] = mapped_column(primary_key=True)
    oi_id: Mapped[int] = mapped_column(ForeignKey("information_objects.id", ondelete="RESTRICT"), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    __table_args__ = (UniqueConstraint("oi_id", "version", name="uq_oi_baseline_version"),
                      Index("ix_baselines_oi_status", "oi_id", "status", "id"))


class ConfigurationChange(Base):
    """Review record; does not execute changes in OpenProject or assets."""
    __tablename__ = "configuration_changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    oi_id: Mapped[int] = mapped_column(ForeignKey("information_objects.id", ondelete="RESTRICT"), nullable=False)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=True)
    change_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="proposed", nullable=False)
    summary: Mapped[str] = mapped_column(String(350), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"), nullable=True)
    openproject_work_package_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now, nullable=False)
    resolution: Mapped[str] = mapped_column(Text, default="", nullable=False)
    __table_args__ = (Index("ix_changes_oi_status", "oi_id", "status", "id"),)


class AssetComponent(Base):
    __tablename__ = "asset_components"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False)
    kind: Mapped[str] = mapped_column(String(35), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    model: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    serial_number: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    inventory_number: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    removal_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    __table_args__ = (Index("ix_comp_asset_active", "asset_id", "removed_at"),
                      Index("ix_comp_serial", "serial_number"),)

class SharedPeripheral(Base):
    __tablename__ = "shared_peripherals"
    id: Mapped[int] = mapped_column(primary_key=True)
    oi_id: Mapped[int] = mapped_column(ForeignKey("information_objects.id", ondelete="RESTRICT"), nullable=False)
    kind: Mapped[str] = mapped_column(String(35), nullable=False)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    ip_address: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    __table_args__ = (Index("ix_peripheral_oi", "oi_id"),)

class AssetPeripheralAccess(Base):
    __tablename__ = "asset_peripheral_access"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False)
    peripheral_id: Mapped[int] = mapped_column(ForeignKey("shared_peripherals.id", ondelete="RESTRICT"), nullable=False)
    allowed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    __table_args__ = (Index("ix_peripheral_access_asset", "asset_id", "revoked_at"),)

class AssetSecurityTool(Base):
    __tablename__ = "asset_security_tools"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    version: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    license_ref: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    expires_on: Mapped[str] = mapped_column(String(10), default="", nullable=False)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    removal_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    __table_args__ = (Index("ix_tools_asset_active", "asset_id", "removed_at"),)

class ServiceRequest(Base):
    __tablename__ = "service_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False)
    reporter: Mapped[str] = mapped_column(String(180), nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    subject: Mapped[str] = mapped_column(String(350), nullable=False)
    fault_description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="open", nullable=False)
    openproject_work_package_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (Index("ix_service_asset_status", "asset_id", "status"),)

class WorkEntry(Base):
    __tablename__ = "work_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False)
    service_request_id: Mapped[int | None] = mapped_column(ForeignKey("service_requests.id", ondelete="RESTRICT"))
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    performer: Mapped[str] = mapped_column(String(180), nullable=False)
    work_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actions: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    seal_state_after: Mapped[str] = mapped_column(String(36), nullable=False)
    seal_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    document_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    __table_args__ = (Index("ix_work_asset_date", "asset_id", "performed_at"),)

class AssetInspection(Base):
    __tablename__ = "asset_inspections"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False)
    inspected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    inspector: Mapped[str] = mapped_column(String(180), nullable=False)
    subject_user: Mapped[str] = mapped_column(String(180), default="", nullable=False)
    checklist: Mapped[dict] = mapped_column(JSON, nullable=False)
    violation_categories: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    finding_summary: Mapped[str] = mapped_column(Text, nullable=False)
    corrective_action: Mapped[str] = mapped_column(Text, default="", nullable=False)
    document_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="review_required", nullable=False)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    __table_args__ = (Index("ix_inspection_asset_date", "asset_id", "inspected_at"),)
