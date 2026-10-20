from datetime import date, datetime, timezone
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def now(): return datetime.now(timezone.utc)

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="admin")
    display_name: Mapped[str] = mapped_column(String(180), default="", nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    attestation_issued_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    attestation_valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    attestation_document_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # legacy; do not remove existing data
    attestation_smb_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    attestation_notice_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    openproject_project_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now, nullable=False)

class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    oi_id: Mapped[int | None] = mapped_column(ForeignKey("information_objects.id", ondelete="RESTRICT"), nullable=True)
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
    savz_name: Mapped[str] = mapped_column(String(200), default='', nullable=False)
    savz_version: Mapped[str] = mapped_column(String(120), default='', nullable=False)
    szi_nsd_name: Mapped[str] = mapped_column(String(200), default='', nullable=False)
    szi_nsd_version: Mapped[str] = mapped_column(String(120), default='', nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now, nullable=False)
    __table_args__ = (Index("ix_assets_oi_id", "oi_id"),Index("ix_assets_serial_number", "serial_number"),Index("ix_assets_inventory_number", "inventory_number"),Index("ix_assets_network_segment", "network_segment"),Index("ix_assets_status", "status"))

class AssetMNI(Base):
    """A physical internal magnetic/solid-state storage medium belonging to an SVT."""
    __tablename__ = 'asset_mni'
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey('assets.id', ondelete='RESTRICT'), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(150), nullable=False)
    accounting_number: Mapped[str] = mapped_column(String(150), nullable=False)
    media_type: Mapped[str] = mapped_column(String(60), default='', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    __table_args__ = (UniqueConstraint('asset_id','serial_number',name='uq_asset_mni_serial'),
                      Index('ix_asset_mni_accounting','accounting_number'),)


class AssetZMNI(Base):
    """An encrypted removable medium assigned to an SVT; container is NOT an MNI."""
    __tablename__ = 'asset_zmni'
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey('assets.id', ondelete='RESTRICT'), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(150), nullable=False)
    accounting_number: Mapped[str] = mapped_column(String(150), nullable=False)
    software_version: Mapped[str] = mapped_column(String(120), default='', nullable=False)
    container_filename: Mapped[str] = mapped_column(String(255), default='', nullable=False)
    container_issued_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    __table_args__ = (UniqueConstraint('asset_id','serial_number',name='uq_asset_zmni_serial'),
                      Index('ix_asset_zmni_accounting','accounting_number'),)


class ZMNIContainerHistory(Base):
    __tablename__ = 'zmni_container_history'
    id: Mapped[int] = mapped_column(primary_key=True)
    zmni_id: Mapped[int] = mapped_column(ForeignKey('asset_zmni.id',ondelete='RESTRICT'),nullable=False)
    container_filename: Mapped[str] = mapped_column(String(255),nullable=False)
    container_issued_on: Mapped[date | None] = mapped_column(Date,nullable=True)
    recorded_by: Mapped[int] = mapped_column(ForeignKey('users.id'),nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now,nullable=False)
    __table_args__ = (Index('ix_zmni_container_history','zmni_id','recorded_at'),)

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
    request_id: Mapped[str] = mapped_column(String(36), default="", nullable=False)
    source_ip: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    user_agent: Mapped[str] = mapped_column(String(256), default="", nullable=False)
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
    manufacturer: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    model: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    inventory_number: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    media_present: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    media_kind: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    media_serial_number: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    media_inventory_number: Mapped[str] = mapped_column(String(150), default="", nullable=False)
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
    connection_type: Mapped[str] = mapped_column(String(32), default="lan", nullable=False)
    driver_name: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    driver_version: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    driver_smb_path: Mapped[str] = mapped_column(String(700), default="", nullable=False)
    driver_sha256: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    driver_document_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
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

class SystemType(Base):
    """Reusable type of application/system in administrative requests."""
    __tablename__ = 'system_types'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class RegistryRequest(Base):
    """General administrative application; not a fault/repair service request."""
    __tablename__ = 'registry_requests'
    id: Mapped[int] = mapped_column(primary_key=True)
    segment: Mapped[str] = mapped_column(String(150), default='', nullable=False)
    full_name: Mapped[str] = mapped_column(String(180), nullable=False)
    system_type_id: Mapped[int | None] = mapped_column(ForeignKey('system_types.id', ondelete='RESTRICT'), nullable=True)  # legacy metadata, hidden in v0.6.2
    ip_address: Mapped[str] = mapped_column(String(60), default='', nullable=False)
    scan_smb_path: Mapped[str] = mapped_column(Text, default='', nullable=False)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey('assets.id', ondelete='RESTRICT'), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    __table_args__ = (Index('ix_registry_requests_segment', 'segment'),
                      Index('ix_registry_requests_type', 'system_type_id'),)


class OIReview(Base):
    """A dated inspection of an information object, with a reference to the full report."""
    __tablename__ = 'oi_reviews'
    id: Mapped[int] = mapped_column(primary_key=True)
    oi_id: Mapped[int] = mapped_column(ForeignKey('information_objects.id', ondelete='RESTRICT'), nullable=False)
    reviewed_on: Mapped[date] = mapped_column(Date, nullable=False)
    reviewer: Mapped[str] = mapped_column(String(180), nullable=False)
    report_smb_path: Mapped[str] = mapped_column(Text, default='', nullable=False)
    notes: Mapped[str] = mapped_column(Text, default='', nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    __table_args__ = (Index('ix_oi_reviews_object_date', 'oi_id', 'reviewed_on'),)


class OIReviewFinding(Base):
    """One separately resolved finding from one OI review. Findings are never deleted."""
    __tablename__ = 'oi_review_findings'
    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey('oi_reviews.id', ondelete='RESTRICT'), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)  # deficiency / violation
    description: Mapped[str] = mapped_column(Text, nullable=False)
    corrective_action: Mapped[str] = mapped_column(Text, default='', nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    __table_args__ = (Index('ix_oi_finding_review_status', 'review_id', 'resolved'),)

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


class OIProposal(Base):
    __tablename__ = "oi_proposals"
    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    classification: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    location: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="submitted", nullable=False)
    review_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_oi_id: Mapped[int | None] = mapped_column(ForeignKey("information_objects.id", ondelete="RESTRICT"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    __table_args__ = (Index("ix_proposals_status_created", "status", "created_at"),)


class PlannedActivity(Base):
    """Local control event; record is not proof of actual inspection or attestation."""
    __tablename__ = "planned_activities"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(35), nullable=False)
    oi_id: Mapped[int] = mapped_column(ForeignKey("information_objects.id", ondelete="RESTRICT"), nullable=False)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=True)
    period_key: Mapped[str] = mapped_column(String(32), nullable=False)
    deadline: Mapped[date] = mapped_column(Date, nullable=False)
    subject: Mapped[str] = mapped_column(String(350), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="open", nullable=False)
    sync_status: Mapped[str] = mapped_column(String(30), default="not_sent", nullable=False)
    openproject_project_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    openproject_work_package_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sync_error: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now, nullable=False)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("control_rules.id", ondelete="RESTRICT"), nullable=True)
    assignee: Mapped[str] = mapped_column(String(180), default="", nullable=False)
    evidence_document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"), nullable=True)
    completion_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    completed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remote_status: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    remote_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (Index("ix_planned_activity_status_deadline", "status", "deadline"),
                      Index("ix_planned_activity_oi", "oi_id", "event_type"))


class ControlRule(Base):
    """Admin-approved periodic control; no claim of regulatory applicability is implied."""
    __tablename__ = "control_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)  # oi or asset
    oi_id: Mapped[int | None] = mapped_column(ForeignKey("information_objects.id", ondelete="RESTRICT"))
    first_due: Mapped[date] = mapped_column(Date, nullable=False)
    interval_months: Mapped[int] = mapped_column(Integer, nullable=False)
    assignee: Mapped[str] = mapped_column(String(180), default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    __table_args__ = (Index("ix_control_rules_active_scope", "active", "scope", "oi_id"),)

class TransferApproval(Base):
    """Single-use authorization for a previously previewed import; no business data stored."""
    __tablename__ = 'oi_transfer_approvals'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    object_code: Mapped[str] = mapped_column(String(80), nullable=False)
    mode: Mapped[str] = mapped_column(String(12), nullable=False)
    archive_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    baseline_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    confirm_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    __table_args__ = (Index('ix_oi_transfer_actor_exp', 'actor_id', 'expires_at'),)
