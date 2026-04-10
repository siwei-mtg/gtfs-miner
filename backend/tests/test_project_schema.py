import pytest
from pydantic import ValidationError

from app.schemas.project import ProjectCreate


def test_valid_defaults():
    p = ProjectCreate()
    assert p.hpm_debut == "07:00"
    assert p.hpm_fin == "09:00"
    assert p.hps_debut == "17:00"
    assert p.hps_fin == "19:30"
    assert p.vacances == "A"
    assert p.pays == "france"


def test_invalid_time_format():
    with pytest.raises(ValidationError):
        ProjectCreate(hpm_debut="25:00")


def test_invalid_vacances():
    with pytest.raises(ValidationError):
        ProjectCreate(vacances="D")


def test_hpm_fin_before_debut():
    with pytest.raises(ValidationError):
        ProjectCreate(hpm_debut="07:00", hpm_fin="06:00")


def test_valid_all_vacances():
    for zone in ("A", "B", "C", "全部"):
        p = ProjectCreate(vacances=zone)
        assert p.vacances == zone
