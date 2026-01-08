import sqlite3

def test_inicjalizuj_baze_idempotent(core_tmp):
    core_tmp.inicjalizuj_baze()
    with sqlite3.connect(core_tmp.BAZA_DANYCH) as c:
        cur = c.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cur.fetchall()}
    expected = {
        "zgloszenia", "zdjecia", "uzytkownicy", "budynki",
        "zgloszenia_logi", "przeglady_techniczne", "uzytkownicy_budynki"
    }
    assert expected.issubset(tables)

def test_konta_startowe_istnieja(core_tmp):
    assert core_tmp.pobierz_uzytkownika_po_loginie("Pracownik")
    assert core_tmp.pobierz_uzytkownika_po_loginie("Technik")
    assert core_tmp.pobierz_uzytkownika_po_loginie("Admin")
