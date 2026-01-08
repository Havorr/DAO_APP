import os
import pytest

def _get(core_tmp, zgl_id):
    z, zdj = core_tmp.pobierz_zgloszenie(zgl_id)
    return z, zdj

@pytest.mark.parametrize("title,opis,prio,kat", [
    ("Awaria sieci","x","NORMAL","IT"),
    ("Zalanie","x","HIGH","Hydraulika"),
    ("Winda","x","CRITICAL","Winda"),
])
def test_flow_create_ticket_variants(core_tmp, ids, title, opis, prio, kat):
    core_tmp.dodaj_zgloszenie(title, opis, [], uzytkownik_id=ids["pracownik_id"], budynek_id=ids["budynek_id"], priorytet=prio, kategoria=kat)
    rows = core_tmp.lista_zgloszen(ids["budynek_id"])
    assert rows[0][1] == title

@pytest.mark.parametrize("bad_title", ["", "   ", None])
def test_dodaj_zgloszenie_wymaga_tytulu(core_tmp, bad_title):
    with pytest.raises(ValueError):
        core_tmp.dodaj_zgloszenie(bad_title, "opis", [])

def test_flow_assign_close_reopen_admin(core_tmp, ids):
    core_tmp.dodaj_zgloszenie("T", "O", [], uzytkownik_id=ids["pracownik_id"], budynek_id=ids["budynek_id"])
    zgl_id = core_tmp.lista_zgloszen(ids["budynek_id"])[0][0]

    assert core_tmp.przypisz_do_technika(zgl_id, ids["technik_id"]) is True
    assert core_tmp.zamknij_zgloszenie(zgl_id, ids["technik_id"]) is True

    z, _ = _get(core_tmp, zgl_id)
    assert z[3] == "DONE"

    assert core_tmp.przypisz_do_technika(zgl_id, ids["admin_id"], force_reopen=True) is True
    z, _ = _get(core_tmp, zgl_id)
    assert z[3] == "IN_PROGRESS"

@pytest.mark.parametrize("prio", ["LOW", "NORMAL", "HIGH", "CRITICAL"])
def test_priorytet_set_all(core_tmp, ids, prio):
    core_tmp.dodaj_zgloszenie(f"T_{prio}", "O", [], uzytkownik_id=ids["pracownik_id"], budynek_id=ids["budynek_id"])
    zgl_id = core_tmp.lista_zgloszen(ids["budynek_id"])[0][0]
    ok = core_tmp.ustaw_priorytet_zgloszenia(zgl_id, prio, uzytkownik_id=ids["admin_id"])
    assert ok is True

@pytest.mark.parametrize("prio", ["", None])
def test_priorytet_falsy_normalizowany(core_tmp, ids, prio):
    core_tmp.dodaj_zgloszenie("T", "O", [], uzytkownik_id=ids["pracownik_id"], budynek_id=ids["budynek_id"])
    zgl_id = core_tmp.lista_zgloszen(ids["budynek_id"])[0][0]
    # w Twoim core to przechodzi (domyślny priorytet)
    assert core_tmp.ustaw_priorytet_zgloszenia(zgl_id, prio, uzytkownik_id=ids["admin_id"]) is True

@pytest.mark.parametrize("prio", ["SUPER", "P0"])
def test_priorytet_invalid_values(core_tmp, ids, prio):
    core_tmp.dodaj_zgloszenie("T", "O", [], uzytkownik_id=ids["pracownik_id"], budynek_id=ids["budynek_id"])
    zgl_id = core_tmp.lista_zgloszen(ids["budynek_id"])[0][0]
    assert core_tmp.ustaw_priorytet_zgloszenia(zgl_id, prio, uzytkownik_id=ids["admin_id"]) is False

@pytest.mark.parametrize("n", [1, 5, 20])
def test_lista_zgloszen_counts(core_tmp, ids, n):
    for i in range(n):
        core_tmp.dodaj_zgloszenie(f"T{i}", "O", [], uzytkownik_id=ids["pracownik_id"], budynek_id=ids["budynek_id"])
    rows = core_tmp.lista_zgloszen(ids["budynek_id"])
    assert len(rows) == n

def test_usun_zgloszenie_usunie_zdjecia_i_pliki(core_tmp, ids, many_files):
    core_tmp.dodaj_zgloszenie("T", "O", [], uzytkownik_id=ids["pracownik_id"], budynek_id=ids["budynek_id"])
    zgl_id = core_tmp.lista_zgloszen(ids["budynek_id"])[0][0]
    core_tmp.dodaj_zdjecia_do_zgloszenia(zgl_id, many_files, uzytkownik_id=ids["admin_id"])
    z, zdj = _get(core_tmp, zgl_id)
    assert len(zdj) == len(many_files)
    for _id, p in zdj:
        assert os.path.exists(p)

    core_tmp.usun_zgloszenie(zgl_id)
    z2, zdj2 = _get(core_tmp, zgl_id)
    assert z2 is None and zdj2 == []
