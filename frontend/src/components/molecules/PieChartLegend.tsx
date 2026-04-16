import React from 'react';
import { cn } from '@/lib/utils';
import { getRouteTypeColor, getRouteTypeLabel } from '@/lib/map-utils';

interface PieChartLegendProps {
  routeTypes: string[];
  className?: string;
}

export const PieChartLegend: React.FC<PieChartLegendProps> = ({ routeTypes, className }) => {
  if (routeTypes.length === 0) return null;
  const sorted = [...routeTypes].sort();
  return (
    <div
      data-testid="pie-chart-legend"
      className={cn(
        'absolute top-[120px] right-2 z-10 bg-background/90 backdrop-blur-sm border border-border rounded-md p-2 space-y-1 text-xs shadow-sm',
        className,
      )}
    >
      <div className="font-semibold text-muted-foreground mb-1">Légende</div>
      {sorted.map((rt) => (
        <div key={rt} className="flex items-center gap-2">
          <span
            className="inline-block w-3 h-3 rounded-full"
            style={{ backgroundColor: getRouteTypeColor(rt) }}
          />
          <span>{getRouteTypeLabel(rt)}</span>
        </div>
      ))}
    </div>
  );
};

PieChartLegend.displayName = 'PieChartLegend';
