from pydantic import BaseModel, ConfigDict, field_validator, ValidationInfo
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
import re

_TIME_RE = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')

class ProjectCreate(BaseModel):
    hpm_debut: str = "07:00"
    hpm_fin:   str = "09:00"
    hps_debut: str = "17:00"
    hps_fin:   str = "19:30"
    vacances:  Literal["A", "B", "C", "全部"] = "A"
    pays:      str = "france"

    @field_validator("hpm_debut", "hpm_fin", "hps_debut", "hps_fin")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        if not _TIME_RE.match(v):
            raise ValueError(f"Format HH:MM attendu, reçu : {v!r}")
        return v

    @field_validator("hpm_fin")
    @classmethod
    def hpm_fin_after_debut(cls, v: str, info: ValidationInfo) -> str:
        debut = info.data.get("hpm_debut")
        if debut and _TIME_RE.match(debut) and v <= debut:
            raise ValueError("hpm_fin doit être postérieur à hpm_debut")
        return v

class ProjectResponse(BaseModel):
    id: str
    status: str
    created_at: datetime
    updated_at: datetime
    parameters: ProjectCreate
    error_message: Optional[str] = None
    reseau: Optional[str] = None
    validite_debut: Optional[int] = None  # YYYYMMDD
    validite_fin: Optional[int] = None  # YYYYMMDD

    model_config = ConfigDict(from_attributes=True)

class WebsocketMessage(BaseModel):
    project_id: str
    status: str
    step: str
    time_elapsed: float
    error: Optional[str] = None
