"""add student submissions

Revision ID: f18334320412
Revises: 95a62308a870
Create Date: 2025-10-17 17:04:05.398083

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f18334320412'
down_revision = '95a62308a870'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'student_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('mimetype', sa.String(length=120), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('content', sa.LargeBinary(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('summary_model', sa.String(length=64), nullable=True),
        sa.Column('summary_updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id']),
        sa.ForeignKeyConstraint(['student_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_submission_assignment_student',
        'student_submissions',
        ['assignment_id', 'student_id'],
        unique=False,
    )

    op.create_table(
        'student_submission_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('submission_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['submission_id'], ['student_submissions.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('student_submission_messages')
    op.drop_index('ix_submission_assignment_student', table_name='student_submissions')
    op.drop_table('student_submissions')
