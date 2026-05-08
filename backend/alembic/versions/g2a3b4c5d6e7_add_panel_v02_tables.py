"""add_panel_v02_tables_and_audit_columns

Revision ID: g2a3b4c5d6e7
Revises: f1a2b3c4d5e6
Create Date: 2026-05-08

Spec §6.3.2 v0.2 additions:
    - panel_feed_diffs (lineage hook)
    - panel_reorg_flags (reorg detector output)
    - panel_dsp_events (DSP timeline from methodology repo)
    - panel_indicators.error_margin_pct + .methodology_commit (audit-grade plumbing)
    - panel_indicators_derived.post_reorg_delta_pct + .methodology_commit
    - panel_networks.has_metro
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g2a3b4c5d6e7'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Audit columns on panel_indicators
    with op.batch_alter_table('panel_indicators', schema=None) as batch_op:
        batch_op.add_column(sa.Column('error_margin_pct', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('methodology_commit', sa.String(), nullable=True))

    # 2. post_reorg_delta_pct + methodology_commit on panel_indicators_derived
    with op.batch_alter_table('panel_indicators_derived', schema=None) as batch_op:
        batch_op.add_column(sa.Column('post_reorg_delta_pct', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('methodology_commit', sa.String(), nullable=True))

    # 3. has_metro on panel_networks (NOT NULL DEFAULT FALSE — backfills existing rows)
    with op.batch_alter_table('panel_networks', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('has_metro', sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    # 4. panel_feed_diffs
    op.create_table(
        'panel_feed_diffs',
        sa.Column('diff_id', sa.String(), nullable=False),
        sa.Column('network_id', sa.String(), nullable=False),
        sa.Column('feed_from_id', sa.String(), nullable=False),
        sa.Column('feed_to_id', sa.String(), nullable=False),
        sa.Column('stops_added', sa.JSON(), nullable=True),
        sa.Column('stops_removed', sa.JSON(), nullable=True),
        sa.Column('stops_modified', sa.JSON(), nullable=True),
        sa.Column('routes_added', sa.JSON(), nullable=True),
        sa.Column('routes_removed', sa.JSON(), nullable=True),
        sa.Column('routes_modified', sa.JSON(), nullable=True),
        sa.Column('stop_jaccard', sa.Float(), nullable=True),
        sa.Column('route_jaccard', sa.Float(), nullable=True),
        sa.Column('computed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['network_id'], ['panel_networks.network_id']),
        sa.ForeignKeyConstraint(['feed_from_id'], ['panel_feeds.feed_id']),
        sa.ForeignKeyConstraint(['feed_to_id'], ['panel_feeds.feed_id']),
        sa.PrimaryKeyConstraint('diff_id'),
    )
    op.create_index('ix_panel_feed_diffs_network_id', 'panel_feed_diffs', ['network_id'])
    op.create_index(
        'ux_panel_feed_diffs_pair', 'panel_feed_diffs',
        ['feed_from_id', 'feed_to_id'], unique=True,
    )

    # 5. panel_reorg_flags
    op.create_table(
        'panel_reorg_flags',
        sa.Column('network_id', sa.String(), nullable=False),
        sa.Column('feed_to_id', sa.String(), nullable=False),
        sa.Column('reorg_detected', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('reorg_severity', sa.String(), nullable=True),
        sa.Column('stop_jaccard', sa.Float(), nullable=True),
        sa.Column('route_jaccard', sa.Float(), nullable=True),
        sa.Column('threshold_version', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('detected_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['network_id'], ['panel_networks.network_id']),
        sa.ForeignKeyConstraint(['feed_to_id'], ['panel_feeds.feed_id']),
        sa.PrimaryKeyConstraint('network_id', 'feed_to_id'),
    )

    # 6. panel_dsp_events
    op.create_table(
        'panel_dsp_events',
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('network_id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('event_date', sa.DateTime(), nullable=False),
        sa.Column('operator_before', sa.String(), nullable=True),
        sa.Column('operator_after', sa.String(), nullable=True),
        sa.Column('contract_id', sa.String(), nullable=True),
        sa.Column('contract_value_eur', sa.Float(), nullable=True),
        sa.Column('boamp_url', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('contributor', sa.String(), nullable=False),
        sa.Column('csv_row_hash', sa.String(), nullable=False),
        sa.Column('imported_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['network_id'], ['panel_networks.network_id']),
        sa.PrimaryKeyConstraint('event_id'),
    )
    op.create_index('ix_panel_dsp_events_network_id', 'panel_dsp_events', ['network_id'])
    op.create_index('ix_panel_dsp_events_event_type', 'panel_dsp_events', ['event_type'])
    op.create_index('ix_panel_dsp_events_event_date', 'panel_dsp_events', ['event_date'])
    op.create_index(
        'ix_panel_dsp_events_csv_row_hash', 'panel_dsp_events',
        ['csv_row_hash'], unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_panel_dsp_events_csv_row_hash', table_name='panel_dsp_events')
    op.drop_index('ix_panel_dsp_events_event_date', table_name='panel_dsp_events')
    op.drop_index('ix_panel_dsp_events_event_type', table_name='panel_dsp_events')
    op.drop_index('ix_panel_dsp_events_network_id', table_name='panel_dsp_events')
    op.drop_table('panel_dsp_events')

    op.drop_table('panel_reorg_flags')

    op.drop_index('ux_panel_feed_diffs_pair', table_name='panel_feed_diffs')
    op.drop_index('ix_panel_feed_diffs_network_id', table_name='panel_feed_diffs')
    op.drop_table('panel_feed_diffs')

    with op.batch_alter_table('panel_networks', schema=None) as batch_op:
        batch_op.drop_column('has_metro')

    with op.batch_alter_table('panel_indicators_derived', schema=None) as batch_op:
        batch_op.drop_column('methodology_commit')
        batch_op.drop_column('post_reorg_delta_pct')

    with op.batch_alter_table('panel_indicators', schema=None) as batch_op:
        batch_op.drop_column('methodology_commit')
        batch_op.drop_column('error_margin_pct')
