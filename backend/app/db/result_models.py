"""
result_models.py — SQLAlchemy models for the 15 GTFS Miner result tables (F-06).

All tables share two structural columns:
  - id          : Integer, auto-increment primary key
  - project_id  : String, FK → projects.id, indexed (enables per-tenant filtering)

Pivot tables (E_1, E_4, F_1, F_3, F_4) are stored in long format (melted):
  the worker transforms the wide-format CSV (columns "1"–"7" for Type_Jour)
  into rows with (type_jour, metric) before insertion.
"""
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from .database import Base


class ResultA1ArretGenerique(Base):
    __tablename__ = "result_a1_arrets_generiques"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    id_ag      = Column(String)
    stop_name  = Column(String)
    stop_lat   = Column(Float)
    stop_lon   = Column(Float)
    id_ag_num  = Column(Integer)


class ResultA2ArretPhysique(Base):
    __tablename__ = "result_a2_arrets_physiques"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    id_ap      = Column(String)
    stop_lat   = Column(Float)
    stop_lon   = Column(Float)
    stop_name  = Column(String)
    id_ag      = Column(String)
    id_ap_num  = Column(Integer)
    id_ag_num  = Column(Integer)


class ResultB1Ligne(Base):
    __tablename__ = "result_b1_lignes"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    project_id       = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    agency_id        = Column(String)
    route_id         = Column(String)
    network_id       = Column(String)
    route_short_name = Column(String)
    route_long_name  = Column(String)
    route_type       = Column(Integer)
    route_color      = Column(String)
    route_text_color = Column(String)
    id_ligne_num     = Column(Integer)
    mode             = Column(String)
    Origin           = Column(String)
    Destination      = Column(String)


class ResultB2SousLigne(Base):
    __tablename__ = "result_b2_sous_lignes"
    id                  = Column(Integer, primary_key=True, autoincrement=True)
    project_id          = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    id_ligne_num        = Column(Integer)
    route_short_name    = Column(String)
    route_long_name     = Column(String)
    sous_ligne          = Column(String)
    id_ag_num_debut     = Column(Integer)
    id_ag_num_terminus  = Column(Integer)
    direction_id        = Column(Integer)
    nb_arrets           = Column(Integer)
    DIST_Vol_Oiseau     = Column(Float)
    ag_origin_name      = Column(String)
    ag_destination_name = Column(String)


class ResultC1Course(Base):
    __tablename__ = "result_c1_courses"
    id                 = Column(Integer, primary_key=True, autoincrement=True)
    project_id         = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    trip_id            = Column(String)
    id_course_num      = Column(Integer)
    id_ligne_num       = Column(Integer)
    sous_ligne         = Column(String)
    id_service_num     = Column(Integer)
    direction_id       = Column(Integer)
    heure_depart       = Column(String)
    h_dep_num          = Column(Float)
    heure_arrive       = Column(String)
    h_arr_num          = Column(Float)
    id_ap_num_debut    = Column(Integer)
    id_ap_num_terminus = Column(Integer)
    id_ag_num_debut    = Column(Integer)
    id_ag_num_terminus = Column(Integer)
    nb_arrets          = Column(Integer)
    DIST_Vol_Oiseau    = Column(Float)


class ResultC2Itineraire(Base):
    __tablename__ = "result_c2_itineraire"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    project_id     = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    id_course_num  = Column(Integer)
    sous_ligne     = Column(String)
    id_ligne_num   = Column(Integer)
    id_service_num = Column(Integer)
    direction_id   = Column(Integer)
    ordre          = Column(Integer)
    id_ap_num      = Column(Integer)
    id_ag_num      = Column(Integer)
    h_dep_num      = Column(Float)
    h_arr_num      = Column(Float)
    TH             = Column(Float)
    heure_depart   = Column(String)
    heure_arrive   = Column(String)


class ResultC3ItineraireArc(Base):
    __tablename__ = "result_c3_itineraire_arc"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    project_id      = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    id_course_num   = Column(Integer)
    sous_ligne      = Column(String)
    id_ligne_num    = Column(Integer)
    id_service_num  = Column(Integer)
    direction_id    = Column(Integer)
    ordre_a         = Column(Integer)
    heure_depart    = Column(String)
    h_dep_num       = Column(Float)
    heure_arrive    = Column(String)
    h_arr_num       = Column(Float)
    id_ap_num_a     = Column(Integer)
    id_ag_num_a     = Column(Integer)
    TH_a            = Column(Float)
    ordre_b         = Column(Integer)
    id_ap_num_b     = Column(Integer)
    id_ag_num_b     = Column(Integer)
    TH_b            = Column(Float)
    DIST_Vol_Oiseau = Column(Float)


class ResultD1ServiceDate(Base):
    __tablename__ = "result_d1_service_dates"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    project_id     = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    service_id     = Column(String)
    id_service_num = Column(Integer)
    Date_GTFS      = Column(String)
    Type_Jour      = Column(Integer)
    Mois           = Column(Integer)
    Annee          = Column(Integer)


class ResultD2ServiceJourtype(Base):
    __tablename__ = "result_d2_service_jourtype"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    project_id     = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    id_ligne_num   = Column(Integer)
    service_id     = Column(String)
    id_service_num = Column(Integer)
    Date_GTFS      = Column(String)
    Type_Jour      = Column(Integer)


# ── Pivot tables stored in long format ────────────────────────────────────────
# The worker melts CSV columns "1"–"7" (Type_Jour values) into (type_jour, metric)

class ResultE1PassageAG(Base):
    __tablename__ = "result_e1_passage_ag"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    id_ag_num  = Column(Integer)
    stop_name  = Column(String)
    stop_lat   = Column(Float)
    stop_lon   = Column(Float)
    type_jour  = Column(Integer)
    nb_passage = Column(Float)


class ResultE4PassageArc(Base):
    __tablename__ = "result_e4_passage_arc"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    project_id  = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    id_ag_num_a = Column(Integer)
    id_ag_num_b = Column(Integer)
    type_jour   = Column(Integer)
    nb_passage  = Column(Float)


class ResultF1CourseLigne(Base):
    __tablename__ = "result_f1_nb_courses_lignes"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    project_id       = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    id_ligne_num     = Column(Integer)
    route_short_name = Column(String)
    route_long_name  = Column(String)
    type_jour        = Column(Integer)
    nb_course        = Column(Float)


class ResultF2CaractSL(Base):
    __tablename__ = "result_f2_caract_sous_lignes"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    project_id       = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    sous_ligne       = Column(String)
    id_ligne_num     = Column(Integer)
    route_short_name = Column(String)
    route_long_name  = Column(String)
    Type_Jour        = Column(Integer)
    Debut            = Column(String)
    Fin              = Column(String)
    Nb_courses       = Column(Integer)
    Duree            = Column(Float)
    Headway_FM       = Column(Float)
    Headway_HPM      = Column(Float)
    Headway_HC       = Column(Float)
    Headway_HPS      = Column(Float)
    Headway_FS       = Column(Float)


class ResultF3KCCLigne(Base):
    __tablename__ = "result_f3_kcc_lignes"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    project_id       = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    id_ligne_num     = Column(Integer)
    route_short_name = Column(String)
    route_long_name  = Column(String)
    type_jour        = Column(Integer)
    kcc              = Column(Float)


class ResultF4KCCSL(Base):
    __tablename__ = "result_f4_kcc_sous_lignes"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    project_id       = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    sous_ligne       = Column(String)
    id_ligne_num     = Column(Integer)
    route_short_name = Column(String)
    route_long_name  = Column(String)
    type_jour        = Column(Integer)
    kcc              = Column(Float)
