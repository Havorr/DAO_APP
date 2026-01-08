import pytest

def test_lista_budynkow_ma_warszawe(core_tmp):
    rows = core_tmp.lista_budynkow()
    assert any(nazwa == "Warszawa" for (_id, nazwa) in rows)

@pytest.mark.parametrize("nazwa,ulica,kod,lp,lw,wyj", [
    ("B1","U","00-001",1,1,1),
    ("B2","U","00-002",10,2,2),
    ("B3","U","00-003",0,0,0),
])
def test_dodaj_budynek_ok_param(core_tmp, nazwa, ulica, kod, lp, lw, wyj):
    bid = core_tmp.dodaj_budynek(nazwa, ulica, kod, liczba_pieter=lp, liczba_wind=lw, wyjscia_na_pietro=wyj)
    b = core_tmp.pobierz_budynek_po_id(bid)
    assert b["nazwa"] == nazwa

def test_dodaj_budynek_bez_nazwy(core_tmp):
    with pytest.raises(ValueError):
        core_tmp.dodaj_budynek("")

def test_dodaj_budynek_duplikat(core_tmp):
    core_tmp.dodaj_budynek("Duplikat", "U", "00-000")
    with pytest.raises(ValueError):
        core_tmp.dodaj_budynek("Duplikat", "U", "00-000")

def test_edytuj_budynek_i_pobierz(core_tmp):
    bid = core_tmp.dodaj_budynek("DoEdycji", "U1", "00-010", stan="OK", opis="x", liczba_pieter=5, liczba_wind=1, wyjscia_na_pietro=2)
    core_tmp.edytuj_budynek(bid, "PoEdycji", "U2", "00-011", stan="S", opis="O", liczba_pieter=6, liczba_wind=2, wyjscia_na_pietro=3)
    b = core_tmp.pobierz_budynek_po_id(bid)
    assert b["nazwa"] == "PoEdycji"
    assert b["kod_pocztowy"] == "00-011"
    assert b["wyjscia_na_pietro"] == 3

def test_usun_budynek_odczepia_zgloszenia(core_tmp, ids):
    bid = core_tmp.dodaj_budynek("BdoUsun", "U", "00-020")
    core_tmp.dodaj_zgloszenie("T", "O", [], uzytkownik_id=ids["pracownik_id"], budynek_id=bid)
    zgl_id = core_tmp.lista_zgloszen(bid)[0][0]
    core_tmp.usun_budynek(bid)
    assert core_tmp.pobierz_budynek_po_id(bid) is None
    with core_tmp.polacz() as c:
        cur = c.cursor()
        cur.execute("SELECT budynek_id FROM zgloszenia WHERE id=?", (zgl_id,))
        assert cur.fetchone()[0] is None
