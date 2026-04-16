import { describe, it, expect } from 'vitest';
import { getRouteTypeColor, generatePieSvg } from '@/lib/map-utils';

describe('map-utils', () => {
  describe('getRouteTypeColor', () => {
    it('should return correct color for known route types', () => {
      expect(getRouteTypeColor('0')).toBe('#42abef');
      expect(getRouteTypeColor('3')).toBe('#00a44d');
    });

    it('should return default color for unknown route types', () => {
      expect(getRouteTypeColor('999')).toBe('#757575');
    });
  });

  describe('generatePieSvg', () => {
    it('should return empty string if no data', () => {
      expect(generatePieSvg({}, 10)).toBe('');
    });

    it('should return a full circle if only one category', () => {
      const svg = generatePieSvg({ '3': 100 }, 10);
      expect(svg).toContain('circle');
      expect(svg).toContain('fill="#00a44d"');
    });

    it('should contain paths if multiple categories', () => {
      const svg = generatePieSvg({ '0': 50, '3': 50 }, 10);
      expect(svg).toContain('path');
      expect(svg).toContain('fill="#42abef"');
      expect(svg).toContain('fill="#00a44d"');
    });

    it('should have correct dimensions', () => {
      const svg = generatePieSvg({ '3': 100 }, 15);
      expect(svg).toContain('width="30"');
      expect(svg).toContain('height="30"');
      expect(svg).toContain('viewBox="0 0 30 30"');
    });
  });
});
