"""
GTFS 文件读取模块 (gtfs_reader.py)

职责：从 ZIP 或本地目录读取 GTFS 原始 .txt 文件，返回 {stem: DataFrame} 字典。
不做任何数据清洗或规范化——I/O 与规范化解耦。

编码检测统一委托给 gtfs_utils.encoding_guess()。
"""
import io
from pathlib import Path
from typing import Dict, Union
from zipfile import ZipFile

import pandas as pd

from .gtfs_utils import encoding_guess


def read_gtfs_zip(zippath: Union[str, Path]) -> Dict[str, pd.DataFrame]:
    """
    从 ZIP 文件读取 GTFS 原始 CSV 数据。

    Output Schema: {file_stem: raw DataFrame}  (e.g. {'stops': df, 'trips': df, ...})
    """
    result: Dict[str, pd.DataFrame] = {}
    with ZipFile(zippath, "r") as zf:
        for name in zf.namelist():
            if not name.endswith('.txt'):
                continue
            stem = Path(name).stem
            raw_bytes = zf.read(name)
            enc = encoding_guess(raw_bytes).get('encoding') or 'utf-8'
            try:
                result[stem] = pd.read_csv(
                    io.BytesIO(raw_bytes), encoding=enc, low_memory=False
                )
            except (UnicodeDecodeError, pd.errors.ParserError):
                result[stem] = pd.read_csv(
                    io.BytesIO(raw_bytes), encoding='latin-1', low_memory=False
                )
    return result


def read_gtfs_dir(dirpath: Union[str, Path]) -> Dict[str, pd.DataFrame]:
    """
    从本地目录读取 GTFS 原始 .txt 文件。

    Output Schema: {file_stem: raw DataFrame}
    """
    result: Dict[str, pd.DataFrame] = {}
    for f in Path(dirpath).glob('*.txt'):
        enc = encoding_guess(f).get('encoding') or 'utf-8'
        try:
            result[f.stem] = pd.read_csv(f, encoding=enc, low_memory=False)
        except (UnicodeDecodeError, pd.errors.ParserError):
            result[f.stem] = pd.read_csv(f, encoding='latin-1', low_memory=False)
    return result
