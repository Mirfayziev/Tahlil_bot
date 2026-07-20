import enum
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class RoleEnum(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMINISTRATOR = "administrator"
    DISPATCHER = "dispatcher"
    DEPARTMENT_HEAD = "bolim_rahbari"
    EXECUTOR = "ijrochi"
    VIEWER = "kuzatuvchi"


class RequestStatus(str, enum.Enum):
    NEW = "yangi"
    ACCEPTED = "qabul_qilindi"
    SENT_TO_EXECUTOR = "ijrochiga_yuborildi"
    IN_PROGRESS = "bajarilmoqda"
    WAITING_INFO = "qoshimcha_malumot_kutilmoqda"
    DONE = "bajarildi"
    CLOSED = "yopildi"
    REJECTED = "rad_etildi"


class Priority(str, enum.Enum):
    URGENT = "shoshilinch"
    HIGH = "yuqori"
    MEDIUM = "orta"
    LOW = "past"


# ---------------------------------------------------------------------------
# Ijrochining bir nechta yo'nalishga (bo'limga) biriktirilishi uchun ko'p-ko'pga jadval
# ---------------------------------------------------------------------------
executor_departments = db.Table(
    "executor_departments",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("department_id", db.Integer, db.ForeignKey("departments.id"), primary_key=True),
)


# ---------------------------------------------------------------------------
# Users (staff: admin / dispatcher / department head / executor / viewer)
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(RoleEnum), nullable=False, default=RoleEnum.VIEWER, index=True)
    phone = db.Column(db.String(30))
    email = db.Column(db.String(150), nullable=True)
    telegram_id = db.Column(db.String(50), unique=True, nullable=True, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True, index=True)
    position = db.Column(db.String(120))  # lavozimi
    is_active_flag = db.Column(db.Boolean, default=True)
    workload = db.Column(db.Integer, default=0)  # joriy yuklama (ochiq ishlar soni)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Login himoyasi (TZ v2, bo'lim 1): ketma-ket noto'g'ri urinishlarni hisoblab,
    # hisobni vaqtincha bloklash uchun.
    failed_login_count = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)

    department = db.relationship("Department", back_populates="users")
    # Ijrochi bir nechta yo'nalishga (bo'limga) biriktirilishi mumkin — masalan
    # "Santexnika va Elektr" + "Konditsioner". Tayinlash/AI avtomatik yo'naltirish
    # shu ro'yxat asosida mos ijrochini tanlaydi (yuqoridagi yagona `department`
    # maydoni esa bo'lim rahbari kabi boshqa rollar uchun ishlatilishda davom etadi).
    departments = db.relationship("Department", secondary=executor_departments, backref="executors")
    assignments = db.relationship("RequestAssignment", back_populates="executor",
                                   foreign_keys="RequestAssignment.executor_id")
    kpi_records = db.relationship("KPIRecord", back_populates="executor")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def is_active(self):
        return self.is_active_flag

    def has_role(self, *roles) -> bool:
        return self.role in roles

    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > datetime.utcnow())

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"

    # Ijrochi bir nechta binoga biriktirilishi mumkin (masalan Markaziy Apparat + Minor).
    buildings = db.relationship("Building", secondary="executor_buildings", backref="executors")


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)

    users = db.relationship("User", back_populates="department")


# Ijrochining bir nechta binoga (masalan Markaziy Apparat + Minor) biriktirilishi uchun
# ko'p-ko'pga jadval.
executor_buildings = db.Table(
    "executor_buildings",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("building_id", db.Integer, db.ForeignKey("buildings.id"), primary_key=True),
)


class Building(db.Model):
    __tablename__ = "buildings"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)

    requests = db.relationship("ServiceRequest", back_populates="building")


# ---------------------------------------------------------------------------
# Customers (Telegram Bot №1 foydalanuvchilari)
# ---------------------------------------------------------------------------
class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(150))
    phone = db.Column(db.String(30))
    language = db.Column(db.String(5), default="uz")  # uz / ru / en
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    requests = db.relationship("ServiceRequest", back_populates="customer")


# ---------------------------------------------------------------------------
# Service categories (self-referential for sub-categories)
# ---------------------------------------------------------------------------
class ServiceCategory(db.Model):
    __tablename__ = "service_categories"

    id = db.Column(db.Integer, primary_key=True)
    name_uz = db.Column(db.String(150), nullable=False)
    name_ru = db.Column(db.String(150))
    name_en = db.Column(db.String(150))
    description = db.Column(db.Text)
    parent_id = db.Column(db.Integer, db.ForeignKey("service_categories.id"), nullable=True, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True, index=True)
    default_priority = db.Column(db.Enum(Priority), default=Priority.MEDIUM)
    default_sla_hours = db.Column(db.Integer, default=24)
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)

    children = db.relationship("ServiceCategory", backref=db.backref("parent", remote_side=[id]))
    department = db.relationship("Department", foreign_keys=[department_id])
    requests = db.relationship("ServiceRequest", back_populates="category",
                                foreign_keys="ServiceRequest.category_id")

    def display_name(self, lang="uz"):
        return {"uz": self.name_uz, "ru": self.name_ru, "en": self.name_en}.get(lang, self.name_uz) or self.name_uz


# ---------------------------------------------------------------------------
# Service requests (Murojaatlar)
# ---------------------------------------------------------------------------
class ServiceRequest(db.Model):
    __tablename__ = "service_requests"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(20), unique=True, nullable=False, index=True)  # masalan REQ-2026-000123

    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("service_categories.id"), nullable=False, index=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), nullable=True, index=True)

    description = db.Column(db.Text, nullable=False)
    address_text = db.Column(db.String(255))
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    # Murojatchi tashkiliy joylashuvi (TZ qo'shimcha talab: lokatsiya o'rniga tashkiliy manzil)
    org_department = db.Column(db.String(150), nullable=True)     # Departament nomi
    org_division = db.Column(db.String(150), nullable=True)       # Boshqarma / Mustaqil boshqarma nomi
    org_is_independent = db.Column(db.Boolean, default=False)     # Mustaqil boshqarmami?
    room_number = db.Column(db.String(30), nullable=True)         # Xona raqami

    status = db.Column(db.Enum(RequestStatus), default=RequestStatus.NEW, nullable=False, index=True)
    priority = db.Column(db.Enum(Priority), default=Priority.MEDIUM, index=True)

    dispatcher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    # AI tahlil natijalari
    ai_suggested_category_id = db.Column(db.Integer, db.ForeignKey("service_categories.id"), nullable=True)
    ai_suggested_priority = db.Column(db.Enum(Priority), nullable=True)
    ai_summary = db.Column(db.Text)
    ai_draft_reply = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    accepted_at = db.Column(db.DateTime, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    deadline_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)

    reject_reason = db.Column(db.Text, nullable=True)

    customer = db.relationship("Customer", back_populates="requests")
    category = db.relationship("ServiceCategory", foreign_keys=[category_id], back_populates="requests")
    building = db.relationship("Building", back_populates="requests")
    dispatcher = db.relationship("User", foreign_keys=[dispatcher_id])

    attachments = db.relationship("RequestAttachment", back_populates="request", cascade="all, delete-orphan")
    assignments = db.relationship("RequestAssignment", back_populates="request", cascade="all, delete-orphan")
    status_logs = db.relationship("RequestStatusLog", back_populates="request", cascade="all, delete-orphan")
    rating = db.relationship("Rating", back_populates="request", uselist=False, cascade="all, delete-orphan")

    @property
    def org_display(self):
        if self.org_is_independent:
            base = f"Mustaqil boshqarma: {self.org_division or '-'}"
        else:
            base = f"{self.org_department or '-'} / {self.org_division or '-'}"
        if self.room_number:
            base += f" (xona {self.room_number})"
        return base

    @property
    def is_overdue(self):
        if self.deadline_at and self.status not in (RequestStatus.DONE, RequestStatus.CLOSED, RequestStatus.REJECTED):
            return datetime.utcnow() > self.deadline_at
        return False

    @property
    def current_executor(self):
        active = [a for a in self.assignments if a.response != "rad_etildi"]
        return active[-1].executor if active else None


class RequestAttachment(db.Model):
    __tablename__ = "request_attachments"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("service_requests.id"), nullable=False)
    file_type = db.Column(db.String(20))  # photo / video / file
    file_ref = db.Column(db.String(500))  # telegram file_id yoki S3 path
    stage = db.Column(db.String(30))  # "murojaat" / "bajarilgan_ish"
    uploaded_by_type = db.Column(db.String(20))  # customer / executor
    uploaded_by_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    request = db.relationship("ServiceRequest", back_populates="attachments")


class RequestAssignment(db.Model):
    __tablename__ = "request_assignments"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("service_requests.id"), nullable=False, index=True)
    executor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    response = db.Column(db.String(20), nullable=True)  # qabul_qilindi / rad_etildi
    reject_reason = db.Column(db.Text, nullable=True)

    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)

    report_text = db.Column(db.Text, nullable=True)
    time_spent_minutes = db.Column(db.Integer, nullable=True)

    extra_time_requested = db.Column(db.Boolean, default=False)
    extra_time_reason = db.Column(db.Text, nullable=True)
    new_deadline = db.Column(db.DateTime, nullable=True)

    request = db.relationship("ServiceRequest", back_populates="assignments")
    executor = db.relationship("User", back_populates="assignments", foreign_keys=[executor_id])


class RequestStatusLog(db.Model):
    __tablename__ = "request_status_logs"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("service_requests.id"), nullable=False, index=True)
    old_status = db.Column(db.String(50))
    new_status = db.Column(db.String(50))
    changed_by_type = db.Column(db.String(20))  # dispatcher / executor / customer / system / ai
    changed_by_id = db.Column(db.Integer, nullable=True)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    request = db.relationship("ServiceRequest", back_populates="status_logs")


class Rating(db.Model):
    __tablename__ = "ratings"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("service_requests.id"), unique=True, nullable=False)
    stars = db.Column(db.Integer, nullable=False)  # 1..5
    comment = db.Column(db.Text, nullable=True)
    suggestion = db.Column(db.Text, nullable=True)  # Xizmatni yaxshilash bo'yicha taklif-so'rov
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    request = db.relationship("ServiceRequest", back_populates="rating")


class KPIRecord(db.Model):
    __tablename__ = "kpi_records"

    id = db.Column(db.Integer, primary_key=True)
    executor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)

    completed_count = db.Column(db.Integer, default=0)
    delayed_count = db.Column(db.Integer, default=0)
    reopened_count = db.Column(db.Integer, default=0)
    avg_completion_minutes = db.Column(db.Float, default=0)
    customer_rating_avg = db.Column(db.Float, default=0)
    manager_rating_avg = db.Column(db.Float, nullable=True)
    kpi_score = db.Column(db.Float, default=0)  # 100 ballik tizim

    executor = db.relationship("User", back_populates="kpi_records")


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    recipient_type = db.Column(db.String(20))  # customer / executor / dispatcher
    recipient_id = db.Column(db.Integer)
    message = db.Column(db.Text, nullable=False)
    channel = db.Column(db.String(20), default="telegram")
    # Ixtiyoriy Telegram inline keyboard (masalan yulduzcha bilan baholash tugmalari).
    # Darhol yuborish (notify.py) muvaffaqiyatsiz bo'lsa, fon workeri (notifier.py)
    # buni saqlangan holda qayta yuborishi uchun bazada saqlanadi.
    reply_markup = db.Column(db.JSON, nullable=True)
    is_sent = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime, nullable=True)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100))
    entity = db.Column(db.String(100))
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
