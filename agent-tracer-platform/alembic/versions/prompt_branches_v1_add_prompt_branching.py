"""add_prompt_branching

Revision ID: prompt_branches_v1
Revises: 6fd1092bc061
Create Date: 2026-07-10 18:22:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'prompt_branches_v1'
down_revision = '6fd1092bc061'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add branch and parent_id columns to prompts table
    op.add_column('prompts', sa.Column('branch', sa.String(255), server_default='main', nullable=False))
    op.add_column('prompts', sa.Column('parent_id', sa.String(255), nullable=True))
    op.create_foreign_key('fk_prompts_parent_id', 'prompts', 'prompts', ['parent_id'], ['id'])
    
    # Update constraints to include branch (Assuming existing unique constraint on project, name, version)
    op.drop_constraint('prompts_project_id_name_version_key', 'prompts', type_='unique')
    op.create_unique_constraint('uq_prompts_project_name_branch_version', 'prompts', ['project_id', 'name', 'branch', 'version'])


def downgrade() -> None:
    op.drop_constraint('uq_prompts_project_name_branch_version', 'prompts', type_='unique')
    op.create_unique_constraint('prompts_project_id_name_version_key', 'prompts', ['project_id', 'name', 'version'])
    
    op.drop_constraint('fk_prompts_parent_id', 'prompts', type_='foreignkey')
    op.drop_column('prompts', 'parent_id')
    op.drop_column('prompts', 'branch')
