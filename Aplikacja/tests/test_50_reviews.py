import pytest

def test_dodaj_przeglad_techniczny_ok(core_tmp, ids):
    core_tmp.dodaj_przeglad_techniczny(ids["budynek_id"], "GAZ", "2025-01-15", "Technik", "uwagi")
    rows = core_tmp.lista_przegladow_dla_budynku(ids["budynek_id"])
    assert len(rows) == 1
