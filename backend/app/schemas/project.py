from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

class ProjectCreate(BaseModel):
    hpm_debut: str = "07:00"
    hpm_fin: str = "09:00"
    hps_debut: str = "17:00"
    hps_fin: str = "19:30"
    vacances: str = "A"
    pays: str = "法国"

class ProjectResponse(BaseModel):
    id: str
    status: str
    created_at: datetime
    updated_at: datetime
    parameters: ProjectCreate
    error_message: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class WebsocketMessage(BaseModel):
    project_id: str
    status: str
    step: str
    time_elapsed: float
    error: Optional[str] = None
