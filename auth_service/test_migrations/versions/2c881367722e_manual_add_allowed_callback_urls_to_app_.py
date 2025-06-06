"""manual_add_allowed_callback_urls_to_app_clients

Revision ID: 2c881367722e
Revises: e43406c0b240
Create Date: <Current Date and Time> # Alembic will fill this in

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2c881367722e'
down_revision: Union[str, None] = 'e43406c0b240'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('app_clients', sa.Column('allowed_callback_urls', postgresql.ARRAY(sa.String()), server_default='{}', nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('app_clients', 'allowed_callback_urls')
    # ### end Alembic commands ###
