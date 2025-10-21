"""add assignment prompts and chat metadata

Revision ID: c4e0a60a139e
Revises: f18334320412
Create Date: 2025-10-20 21:02:01.510424

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4e0a60a139e'
down_revision = 'f18334320412'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'assignment_prompts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('prompt_text', sa.Text(), nullable=False),
        sa.Column('example_response', sa.Text(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id']),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('student_submission_messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('model', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('context', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('student_submission_messages', schema=None) as batch_op:
        batch_op.drop_column('context')
        batch_op.drop_column('model')

    op.drop_table('assignment_prompts')
