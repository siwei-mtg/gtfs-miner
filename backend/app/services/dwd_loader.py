"""DWD SQLite loader — 将 14 个 CSV 输出加载至项目专属 SQLite，供 LLM Agent 查询。"""
from pathlib import Path
import sqlite3
import pandas as pd


# (csv_filename → (sqlite_table_name, id_vars_or_None, value_name_or_None))
# id_vars=None 表示直接加载（不 melt）；E_4 用 None 触发自动检测所有非数字列
_DWD_MAP: dict[str, tuple] = {
    "A_1_Arrets_Generiques.csv":     ("arrets_generiques",   None, None),
    "A_2_Arrets_Physiques.csv":      ("arrets_physiques",    None, None),
    "B_1_Lignes.csv":                ("lignes",              None, None),
    "B_2_Sous_Lignes.csv":           ("sous_lignes",         None, None),
    "C_1_Courses.csv":               ("courses",             None, None),
    "C_2_Itineraire.csv":            ("itineraire",          None, None),
    "C_3_Itineraire_Arc.csv":        ("itineraire_arc",      None, None),
    "D_1_Service_Dates.csv":         ("service_dates",       None, None),
    "D_2_Service_Jourtype.csv":      ("service_jourtype",    None, None),
    # pivot: 宽列 "1"–"7" → long (jour_type, metric)
    "E_1_Nombre_Passage_AG.csv":     ("passage_ag",
                                      ["id_ag_num", "stop_name", "stop_lat", "stop_lon"],
                                      "nb_passages"),
    "E_4_Nombre_Passage_Arc.csv":    ("passage_arc",
                                      None,   # 自动检测所有非数字列为 id_vars
                                      "nb_passages"),
    "F_1_Nombre_Courses_Lignes.csv": ("nb_courses_lignes",
                                      ["id_ligne_num", "route_short_name", "route_long_name"],
                                      "nb_courses"),
    "F_2_Caract_SousLignes.csv":     ("caract_sous_lignes",  None, None),
    "F_3_KCC_Lignes.csv":            ("kcc_lignes",
                                      ["id_ligne_num", "route_short_name", "route_long_name"],
                                      "kcc_km"),
    "F_4_KCC_Sous_Ligne.csv":        ("kcc_sous_ligne",
                                      ["sous_ligne", "id_ligne_num", "route_short_name", "route_long_name"],
                                      "kcc_km"),
}

_PIVOT_FILES: frozenset[str] = frozenset({
    "E_1_Nombre_Passage_AG.csv",
    "E_4_Nombre_Passage_Arc.csv",
    "F_1_Nombre_Courses_Lignes.csv",
    "F_3_KCC_Lignes.csv",
    "F_4_KCC_Sous_Ligne.csv",
})


def load_outputs_to_dwd(project_id: str, output_dir: Path) -> Path:
    """
    将 output_dir 下 14 个 CSV 加载至 {output_dir}/{project_id}_query.sqlite。

    E_*/F_* 文件在加载前调用 pd.melt() 将日类型透视列转为规范行格式：
      - var_name: "jour_type"
      - value_name: 依文件而定（nb_passages / nb_courses / kcc_km）

    幂等：每次重跑先 DROP TABLE 再写入，行数不翻倍。
    返回 SQLite 文件路径。
    """
    sqlite_path = output_dir / f"{project_id}_query.sqlite"
    con = sqlite3.connect(sqlite_path)
    try:
        for csv_name, (table_name, id_vars, value_name) in _DWD_MAP.items():
            csv_path = output_dir / csv_name
            if not csv_path.exists():
                continue

            df = pd.read_csv(csv_path, sep=";", encoding="utf-8-sig")

            if csv_name in _PIVOT_FILES:
                pivot_cols = [c for c in df.columns if str(c).isdigit()]
                if pivot_cols:
                    if id_vars is not None:
                        keep = [c for c in id_vars if c in df.columns]
                    else:
                        # Auto-detect: toutes les colonnes non-numériques
                        keep = [c for c in df.columns if not str(c).isdigit()]
                    df = df[keep + pivot_cols].melt(
                        id_vars=keep, var_name="jour_type", value_name=value_name
                    )

            # Idempotency: supprimer avant réinsertion
            con.execute(f"DROP TABLE IF EXISTS [{table_name}]")
            df.to_sql(table_name, con, if_exists="replace", index=False)

        con.commit()
    finally:
        con.close()

    return sqlite_path
