Great question! Here's how the **Bandwidth on network links** feature works in AequilibraE:

## Concept

It takes your **network link geometries** and creates a new **polygon layer** where each link is represented as a **buffer (polygon)** whose width is proportional to a chosen variable — like assigned traffic volume.

---

## How it Works Step by Step

### 1. Input Requirements
- A **line layer** (your network links)
- A **numeric field** in that layer (e.g., `volume`, `AB_vol`, `flow`)
- A **scale factor** to convert values to map units

### 2. Geometry Transformation
Each line arc is **offset and buffered** to create a visual bandwidth:

```
buffer_width = field_value × scale_factor
```

The line is typically **offset to one side** (left or right), so that:
- **AB direction** → draws on one side
- **BA direction** → draws on the other side

This avoids overlap on bidirectional links and makes the map readable.

### 3. Output
A new **polygon layer** is created where:
- Each polygon represents one link
- The **width of the polygon** reflects the variable value
- You can style it with color, transparency, etc.

---

## Visual Result

```
Original link:     ──────────────────
                   
With bandwidth:   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓   ← width ∝ volume
```

For bidirectional:
```
                  ▓▓▓▓▓ AB flow (e.g. 3000 veh)
    link center   ──────────────────────
                  ██ BA flow (e.g. 800 veh)
```

---

## Key Parameters

| Parameter | Description |
|---|---|
| **Layer** | The network link layer |
| **Field** | Numeric variable to drive width |
| **Scale factor** | Multiplier: value × scale = width in map units |
| **Offset** | Which side to draw (AB/BA) |
| **Minimum width** | Optional floor so tiny values still show |

---

## Python / Scripting Side

In the standalone AequilibraE library, this is handled via the `plot` or geometry utilities. You can also replicate it manually:

```python
from qgis.core import QgsGeometry
# Pseudo-logic:
buffer_width = feature['volume'] * scale_factor
polygon = line_geometry.buffer(buffer_width, segments=2)
```

---

## Tips

- **Scale factor** is the trickiest part — it depends on your CRS units (degrees vs metres)
- If your CRS is in **metres**, a scale of `0.00005` for volumes in the thousands works as a starting point
- Always use a **projected CRS** (not WGS84) for accurate widths

---

Would you like help choosing a scale factor, or are you working through a specific assignment result you want to visualize?