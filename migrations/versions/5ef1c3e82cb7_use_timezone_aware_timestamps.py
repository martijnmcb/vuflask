"""use timezone aware timestamps

Revision ID: 5ef1c3e82cb7
Revises: c4e0a60a139e
Create Date: 2025-10-27 10:58:16.798871

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5ef1c3e82cb7'
down_revision = 'c4e0a60a139e'
branch_labels = None
depends_on = None


TIMESTAMP_COLUMNS = (
    ("users", "created_at", True),
    ("connection_settings", "updated_at", True),
    ("connection_profiles", "updated_at", True),
    ("assignments", "created_at", True),
    ("assignment_documents", "uploaded_at", True),
    ("assignment_documents", "summary_updated_at", True),
    ("assignment_prompts", "created_at", True),
    ("assignment_prompts", "updated_at", True),
    ("student_submissions", "uploaded_at", True),
    ("student_submissions", "summary_updated_at", True),
    ("student_submission_messages", "created_at", True),
)


def upgrade():
    tz_type = sa.DateTime(timezone=True)
    naive_type = sa.DateTime()

    for table_name, column_name, is_nullable in TIMESTAMP_COLUMNS:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.alter_column(
                column_name,
                existing_type=naive_type,
                type_=tz_type,
                existing_nullable=is_nullable,
            )


def downgrade():
    tz_type = sa.DateTime(timezone=True)
    naive_type = sa.DateTime()

    for table_name, column_name, is_nullable in reversed(TIMESTAMP_COLUMNS):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.alter_column(
                column_name,
                existing_type=tz_type,
                type_=naive_type,
                existing_nullable=is_nullable,
            )
