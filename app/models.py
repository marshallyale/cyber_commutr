from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db, login
from datetime import datetime, timezone
from argon2 import PasswordHasher
from flask_login import UserMixin

PH = PasswordHasher()


class User(UserMixin, db.Model):
    # def __init__(self):
    #     self.ph = PasswordHasher()
    #     self.password_hash = None

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(
        sa.String(64), index=True, unique=True
    )
    email: so.Mapped[str] = so.mapped_column(
        sa.String(255), index=True, unique=True
    )
    password: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    # refresh_token: so.Mapped[str] = so.mapped_column(sa.String(64))
    # refresh_token_exp: so.Mapped[datetime] = so.mapped_column(
    #     sa.TIMESTAMP(timezone=False)
    # )
    created_at: so.Mapped[datetime] = so.mapped_column(
        sa.TIMESTAMP(timezone=False),
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: so.Mapped[datetime] = so.mapped_column(
        sa.TIMESTAMP(timezone=False),
        default=lambda: datetime.now(timezone.utc),
    )

    def set_password(self, password):
        self.password = PH.hash(password)

    def check_password(self, password):
        print(self.password)
        return PH.verify(self.password, password)


@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))
