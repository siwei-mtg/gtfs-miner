# Plan: Pandera Schema Implementation (DATA_MODEL_REPORT Step 1+2)

## Context

`DATA_MODEL_REPORT.md` defines a two-layer data model strategy for GTFS Miner. This plan implements Step 1 (create `gtfs_schemas.py`) and Step 2 (add `.validate()` at module output boundaries), then updates the report to document the result. No existing schema file or `pandera` dependency exists yet.

---

## Files to Create / Modify

| File | Action |
| :--- | :--- |
| `backend/requirements.txt` | Add `pandera>=0.18` |
| `gtfs_schemas.py` (new) | Define 5 core schemas |
| `gtfs_spatial.py` | Add import + 3 validate calls |
| `gtfs_generator.py` | Add import + 4 validate calls |
| `DATA_MODEL_REPORT.md` | Add section 7 implementation record |

---

## Step 1 — Add pandera to requirements

**File:** `backend/requirements.txt`

Add after `chardet==5.2.0`:
```text
pandera>=0.18
```

---

## Step 2 — Create gtfs_schemas.py

**File:** `gtfs_schemas.py` (project root, alongside other `gtfs_*.py` modules)

Schema definitions, adjusted from report to match actual column structure found in code:

### APSchema
Actual columns from all 3 generation paths: `id_ap`, `id_ag`, `id_ap_num`, `id_ag_num`, `stop_name`, `stop_lat`, `stop_lon`

```python
APSchema = DataFrameSchema({
    "id_ap":     Column(str, nullable=False),
    "id_ag":     Column(str, nullable=False),
    "id_ap_num": Column(int, Check.ge(100000), nullable=False),
    "id_ag_num": Column(int, Check.ge(10000),  nullable=False),
    "stop_name": Column(str),
    "stop_lat":  Column(float, Check.in_range(-90, 90)),
    "stop_lon":  Column(float, Check.in_range(-180, 180)),
}, coerce=True)
```

### AGSchema
Same across all generation paths: `id_ag`, `id_ag_num`, `stop_name`, `stop_lat`, `stop_lon`

```python
AGSchema = DataFrameSchema({
    "id_ag":     Column(str, nullable=False),
    "id_ag_num": Column(int, Check.ge(10000), nullable=False),
    "stop_name": Column(str),
    "stop_lat":  Column(float, Check.in_range(-90, 90)),
    "stop_lon":  Column(float, Check.in_range(-180, 180)),
}, coerce=True)
```

### ItineraireSchema
From `itineraire_generate` return cols (line 53-55):
`id_course_num`, `id_ligne_num`, `id_service_num`, `direction_id`, `stop_sequence`, `id_ap_num`, `id_ag_num`, `arrival_time`, `departure_time`, `TH`, `trip_headsign`

```python
ItineraireSchema = DataFrameSchema({
    "id_course_num":  Column(int, nullable=False),
    "id_ligne_num":   Column(int, nullable=False),
    "id_service_num": Column(int, nullable=False),
    "direction_id":   Column(int),
    "stop_sequence":  Column(int, Check.ge(1)),
    "id_ap_num":      Column(int, nullable=False),
    "id_ag_num":      Column(int, nullable=False),
    "arrival_time":   Column(float),
    "departure_time": Column(float),
    "TH":             Column(int),
    "trip_headsign":  Column(str),
}, coerce=True)
```

### CourseSchema
From `course_generate` (line 158-194). Actual columns include `trip_headsign` and `DIST_Vol_Oiseau` (missing from report draft):

```python
CourseSchema = DataFrameSchema({
    "id_course_num":      Column(int, nullable=False),
    "id_ligne_num":       Column(int, nullable=False),
    "id_service_num":     Column(int),
    "direction_id":       Column(int),
    "trip_headsign":      Column(str),
    "heure_depart":       Column(float),
    "heure_arrive":       Column(float),
    "id_ap_num_debut":    Column(int),
    "id_ap_num_terminus": Column(int),
    "id_ag_num_debut":    Column(int),
    "id_ag_num_terminus": Column(int),
    "nb_arrets":          Column(int, Check.ge(1)),
    "DIST_Vol_Oiseau":    Column(float, Check.ge(0)),
    "sous_ligne":         Column(str, nullable=False),
}, coerce=True)
```

### ItiArcSchema
From `itiarc_generate` return (lines 232-241). Report draft was incomplete — actual output has 15 columns:

```python
ItiArcSchema = DataFrameSchema({
    "id_course_num":  Column(int, nullable=False),
    "id_ligne_num":   Column(int, nullable=False),
    "id_service_num": Column(int, nullable=False),
    "direction_id":   Column(int),
    "ordre_a":        Column(int),
    "heure_depart":   Column(float),
    "id_ap_num_a":    Column(int, nullable=False),
    "id_ag_num_a":    Column(int, nullable=False),
    "TH_a":           Column(int),
    "ordre_b":        Column(int),
    "heure_arrive":   Column(float),
    "id_ap_num_b":    Column(int, nullable=False),
    "id_ag_num_b":    Column(int, nullable=False),
    "TH_b":           Column(int),
    "DIST_Vol_Oiseau": Column(float, Check.ge(0)),
}, coerce=True)
```

> [!NOTE]
> `ServiceDateSchema` is kept as in the report. `coerce=True` on all schemas handles the `id_ag_num` float→int drift risk identified in the report.

---

## Step 3 — Modify gtfs_spatial.py

**Critical constraint:** Early-exit returns (lines 35, 79) return an empty `pd.DataFrame()` for AG — do **NOT** validate these paths. Only add `.validate()` on the primary return of each function.

Add import after existing imports (line 23):
```python
from gtfs_schemas import APSchema, AGSchema
```

Three validate sites:

| Function | Line | Change |
| :--- | :--- | :--- |
| `ag_ap_generate_bigvolume` | 67 | `return APSchema.validate(AP), AGSchema.validate(AG)` |
| `ag_ap_generate_hcluster` | 96 | `return APSchema.validate(AP), AGSchema.validate(AG)` |
| `ag_ap_generate_asit` | 125 | `return APSchema.validate(AP), AGSchema.validate(AG)` |

`ag_ap_generate_reshape` (line 159) delegates to the above — no validate needed there.

---

## Step 4 — Modify gtfs_generator.py

Add import after existing imports (line 27):
```python
from gtfs_schemas import ItineraireSchema, CourseSchema, ItiArcSchema, ServiceDateSchema
```

Four validate sites:

| Function | Line | Change |
| :--- | :--- | :--- |
| `itineraire_generate` | 59 | `return ItineraireSchema.validate(itineraire)` |
| `service_date_generate` | 148 | `return ServiceDateSchema.validate(cal_final), msg_date` |
| `course_generate` | 194 | `return CourseSchema.validate(course)` |
| `itiarc_generate` | 236–241 | Assign result to variable, validate, then return |

For `itiarc_generate`, the return is an inline expression. Refactor to:
```python
result = arc_dist[cols].rename(columns={
    'stop_sequence_a': 'ordre_a',
    'departure_time':  'heure_depart',
    'stop_sequence_b': 'ordre_b',
    'arrival_time':    'heure_arrive',
})
return ItiArcSchema.validate(result)
```

---

## Step 5 — Update DATA_MODEL_REPORT.md

Add **Section 7 — 实施记录** at end of document, documenting:
- Implementation date (2026-04-03)
- Step 1+2 complete: files created/modified, line numbers
- Schema adjustments vs report draft (`CourseSchema` added `trip_headsign` + `DIST_Vol_Oiseau`; `ItiArcSchema` expanded to 15 columns)
- Next: Step 3 (test integration) and Step 4 (API models) remain pending

---

## Verification

After implementation:

1. **Install pandera**
   ```bash
   pip install pandera>=0.18
   ```

2. **Run existing tests** (should still pass — `validate()` is transparent on valid data)
   ```bash
   python -m pytest test_gtfs_core.py -v
   ```

3. **Smoke test spatial module**
   ```bash
   python gtfs_spatial.py
   ```

4. **Smoke test generator module**
   ```bash
   python gtfs_generator.py
   ```

If schemas catch a real constraint violation, `pandera` raises `SchemaError` with the specific column and row — this is the intended behavior.