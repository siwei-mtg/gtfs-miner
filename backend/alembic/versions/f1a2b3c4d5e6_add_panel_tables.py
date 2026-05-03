"""add_panel_tables

Revision ID: f1a2b3c4d5e6
Revises: 0860c465c5b6
Create Date: 2026-05-03

Spec §6.3 storage schema for compare-transit.fr panel:
    panel_networks, panel_feeds, panel_indicators, panel_indicators_derived,
    panel_quality, panel_peer_groups
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = '0860c465c5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # panel_networks
    op.create_table(
        'panel_networks',
        sa.Column('network_id', sa.String(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('pan_dataset_id', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('aom_id', sa.String(), nullable=True),
        sa.Column('tier', sa.String(), nullable=True),
        sa.Column('population', sa.Integer(), nullable=True),
        sa.Column('area_km2', sa.Float(), nullable=True),
        sa.Column('first_feed_date', sa.DateTime(), nullable=True),
        sa.Column('last_feed_date', sa.DateTime(), nullable=True),
        sa.Column('history_depth_months', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('network_id'),
    )
    op.create_index('ix_panel_networks_slug', 'panel_networks', ['slug'], unique=True)
    op.create_index('ix_panel_networks_pan_dataset_id', 'panel_networks', ['pan_dataset_id'], unique=True)
    op.create_index('ix_panel_networks_aom_id', 'panel_networks', ['aom_id'])
    op.create_index('ix_panel_networks_tier', 'panel_networks', ['tier'])

    # panel_feeds
    op.create_table(
        'panel_feeds',
        sa.Column('feed_id', sa.String(), nullable=False),
        sa.Column('network_id', sa.String(), nullable=False),
        sa.Column('pan_resource_id', sa.String(), nullable=False),
        sa.Column('pan_resource_history_id', sa.String(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=False),
        sa.Column('feed_start_date', sa.DateTime(), nullable=False),
        sa.Column('feed_end_date', sa.DateTime(), nullable=True),
        sa.Column('feed_info_sha256', sa.String(), nullable=True),
        sa.Column('feed_info_source', sa.String(), nullable=True),
        sa.Column('gtfs_url', sa.String(), nullable=False),
        sa.Column('r2_path', sa.String(), nullable=True),
        sa.Column('checksum_sha256', sa.String(), nullable=True),
        sa.Column('filesize', sa.Integer(), nullable=True),
        sa.Column('process_status', sa.String(), nullable=True),
        sa.Column('process_duration_s', sa.Float(), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['network_id'], ['panel_networks.network_id']),
        sa.PrimaryKeyConstraint('feed_id'),
    )
    op.create_index('ix_panel_feeds_network_id', 'panel_feeds', ['network_id'])
    op.create_index('ix_panel_feeds_pan_resource_id', 'panel_feeds', ['pan_resource_id'])
    op.create_index('ix_panel_feeds_pan_resource_history_id', 'panel_feeds', ['pan_resource_history_id'])
    op.create_index('ix_panel_feeds_published_at', 'panel_feeds', ['published_at'])
    op.create_index('ix_panel_feeds_feed_start_date', 'panel_feeds', ['feed_start_date'])
    op.create_index('ix_panel_feeds_feed_info_sha256', 'panel_feeds', ['feed_info_sha256'])
    op.create_index('ix_panel_feeds_process_status', 'panel_feeds', ['process_status'])
    op.create_index(
        'ux_panel_feeds_network_fsd', 'panel_feeds',
        ['network_id', 'feed_start_date'], unique=True,
    )

    # panel_indicators (compound PK: feed_id + indicator_id)
    op.create_table(
        'panel_indicators',
        sa.Column('feed_id', sa.String(), nullable=False),
        sa.Column('indicator_id', sa.String(), nullable=False),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('unit', sa.String(), nullable=False),
        sa.Column('computed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['feed_id'], ['panel_feeds.feed_id']),
        sa.PrimaryKeyConstraint('feed_id', 'indicator_id'),
    )
    op.create_index('ix_panel_indicators_indicator_id', 'panel_indicators', ['indicator_id'])

    # panel_indicators_derived
    op.create_table(
        'panel_indicators_derived',
        sa.Column('feed_id', sa.String(), nullable=False),
        sa.Column('indicator_id', sa.String(), nullable=False),
        sa.Column('zscore', sa.Float(), nullable=True),
        sa.Column('percentile', sa.Float(), nullable=True),
        sa.Column('yoy_delta_pct', sa.Float(), nullable=True),
        sa.Column('peer_group_size', sa.Integer(), nullable=True),
        sa.Column('computed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['feed_id'], ['panel_feeds.feed_id']),
        sa.PrimaryKeyConstraint('feed_id', 'indicator_id'),
    )
    op.create_index('ix_panel_indicators_derived_indicator_id', 'panel_indicators_derived', ['indicator_id'])

    # panel_quality
    op.create_table(
        'panel_quality',
        sa.Column('feed_id', sa.String(), nullable=False),
        sa.Column('validator_errors', sa.JSON(), nullable=True),
        sa.Column('overall_grade', sa.String(), nullable=True),
        sa.Column('overall_score', sa.Float(), nullable=True),
        sa.Column('computed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['feed_id'], ['panel_feeds.feed_id']),
        sa.PrimaryKeyConstraint('feed_id'),
    )

    # panel_peer_groups
    op.create_table(
        'panel_peer_groups',
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('definition', sa.JSON(), nullable=True),
        sa.Column('member_count', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('group_id'),
    )


def downgrade() -> None:
    op.drop_table('panel_peer_groups')
    op.drop_table('panel_quality')
    op.drop_index('ix_panel_indicators_derived_indicator_id', table_name='panel_indicators_derived')
    op.drop_table('panel_indicators_derived')
    op.drop_index('ix_panel_indicators_indicator_id', table_name='panel_indicators')
    op.drop_table('panel_indicators')
    op.drop_index('ux_panel_feeds_network_fsd', table_name='panel_feeds')
    op.drop_index('ix_panel_feeds_process_status', table_name='panel_feeds')
    op.drop_index('ix_panel_feeds_feed_info_sha256', table_name='panel_feeds')
    op.drop_index('ix_panel_feeds_feed_start_date', table_name='panel_feeds')
    op.drop_index('ix_panel_feeds_published_at', table_name='panel_feeds')
    op.drop_index('ix_panel_feeds_pan_resource_history_id', table_name='panel_feeds')
    op.drop_index('ix_panel_feeds_pan_resource_id', table_name='panel_feeds')
    op.drop_index('ix_panel_feeds_network_id', table_name='panel_feeds')
    op.drop_table('panel_feeds')
    op.drop_index('ix_panel_networks_tier', table_name='panel_networks')
    op.drop_index('ix_panel_networks_aom_id', table_name='panel_networks')
    op.drop_index('ix_panel_networks_pan_dataset_id', table_name='panel_networks')
    op.drop_index('ix_panel_networks_slug', table_name='panel_networks')
    op.drop_table('panel_networks')
