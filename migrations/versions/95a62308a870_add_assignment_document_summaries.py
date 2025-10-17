"""add assignment document summaries

Revision ID: 95a62308a870
Revises: b4a14fbb86f9
Create Date: 2025-10-17 12:36:05.177858

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '95a62308a870'
down_revision = 'b4a14fbb86f9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('assignment_documents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('summary', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('summary_model', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('summary_updated_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('assignment_documents', schema=None) as batch_op:
        batch_op.drop_column('summary_updated_at')
        batch_op.drop_column('summary_model')
        batch_op.drop_column('summary')
