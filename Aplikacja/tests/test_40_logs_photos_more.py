import os
import pytest

@pytest.mark.parametrize("n", [0, 1, 5, 20])
def test_logs_insert_count(core_tmp, ids, n):
    core_tmp.dodaj_zgloszenie("LOGS", "O", [], uzytkownik_id=ids["pracownik_id"], budynek_id=ids["budynek_id"])
    zgl_id = core_tmp.lista_zgloszen(ids["budynek_id"])[0][0]
    for i in range(n):
        core_tmp.dodaj_log(zgl_id, ids["admin_id"], "COMMENT_PUBLIC", f"x{i}")
    rows = core_tmp.pobierz_logi(zgl_id, rola="ADMIN")
    # w logach powinien być CREATE + ewentualne komentarze
    assert len(rows) >= 1 + n

def test_logs_internal_hidden_for_worker(core_tmp, ids):
    core_tmp.dodaj_zgloszenie("LOGS", "O", [], uzytkownik_id=ids["pracownik_id"], budynek_id=ids["budynek_id"])
    zgl_id = core_tmp.lista_zgloszen(ids["budynek_id"])[0][0]
    core_tmp.dodaj_log(zgl_id, ids["admin_id"], "COMMENT_INTERNAL", "tajne")
    rows = core_tmp.pobierz_logi(zgl_id, rola="PRACOWNIK")
    assert all(t != "COMMENT_INTERNAL" for (_c,_l,t,_s) in rows)

@pytest.mark.parametrize("count", [1, 5, 10])
def test_photos_add_and_delete_roundtrip(core_tmp, ids, tmp_path, count):
    core_tmp.dodaj_zgloszenie("PH", "O", [], uzytkownik_id=ids["pracownik_id"], budynek_id=ids["budynek_id"])
    zgl_id = core_tmp.lista_zgloszen(ids["budynek_id"])[0][0]

    src = []
    for i in range(count):
        p = tmp_path / f"s{i}.bin"
        p.write_bytes(b"z")
        src.append(str(p))

    core_tmp.dodaj_zdjecia_do_zgloszenia(zgl_id, src, uzytkownik_id=ids["admin_id"])
    _, zdj = core_tmp.pobierz_zgloszenie(zgl_id)
    assert len(zdj) == count

    # usuń pierwsze
    first_path = zdj[0][1]
    assert os.path.exists(first_path)
    core_tmp.usun_zdjecie_ze_zgloszenia(zgl_id, first_path, uzytkownik_id=ids["admin_id"])
    assert not os.path.exists(first_path)
