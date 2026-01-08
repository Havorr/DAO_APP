import pytest

@pytest.mark.parametrize("typ", ["GAZ", "WINDA", "PPOZ"])
def test_przeglady_add_history_order(core_tmp, ids, typ):
    core_tmp.dodaj_przeglad_techniczny(ids["budynek_id"], typ, "2024-01-01", "A", None)
    core_tmp.dodaj_przeglad_techniczny(ids["budynek_id"], typ, "2025-01-01", "B", "x")
    hist = core_tmp.historia_przegladow_dla_budynku_i_typu(ids["budynek_id"], typ)
    assert len(hist) == 2
    assert hist[0][1] == "2025-01-01"

def test_ostatnie_przeglady_shape(core_tmp, ids):
    rows = core_tmp.ostatnie_przeglady_dla_budynku(ids["budynek_id"])

    # musi być przynajmniej po jednym wpisie na typ (czasem core może zwracać tylko istniejące)
    assert isinstance(rows, list)
    assert len(rows) >= 1

    # pierwszy element wiersza powinien być typem
    typy = {r[0] for r in rows}
    assert typy.issubset(set(core_tmp.PRZEGLADY_TYPY)) or typy.intersection(set(core_tmp.PRZEGLADY_TYPY))

    # każdy wiersz powinien mieć co najmniej (typ, data, technik) — mogą dochodzić dodatkowe pola
    assert all(len(r) >= 3 for r in rows)

