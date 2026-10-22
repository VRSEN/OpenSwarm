"""Alembic migration: Integrity Engine reputation tables."""

revision = "001_reputation_integrity"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Tables created via SQLAlchemy create_all in development.
    # Run: python -m backend.seed
    pass


def downgrade():
    pass
