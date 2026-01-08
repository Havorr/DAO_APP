import os

def test_dodaj_zgloszenie_kopiuje_zdjecia(core_tmp, ids, dummy_photo):
    core_tmp.dodaj_zgloszenie("Z", "O", [dummy_photo], uzytkownik_id=ids["pracownik_id"], budynek_id=ids["budynek_id"])
    zgl_id = core_tmp.lista_zgloszen(ids["budynek_id"])[0][0]
    z, zdj = core_tmp.pobierz_zgloszenie(zgl_id)
    assert len(zdj) == 1
    assert os.path.exists(zdj[0][1])
