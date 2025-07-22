from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import UUID
import uuid

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    __table_args__ = (
        db.Index('idx_users_email', 'email'),
        db.Index('idx_users_stripe_customer', 'stripe_customer_id'),
        db.Index('idx_users_subscription', 'subscription_status'),
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    stripe_customer_id = db.Column(db.String(255), unique=True)
    subscription_status = db.Column(db.String(50), default='free')
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
