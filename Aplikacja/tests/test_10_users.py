import pytest

@pytest.mark.parametrize("login,haslo,rola", [
    ("U1","a","PRACOWNIK"),
    ("U2","b","TECHNIK"),
    ("U3","c","ADMIN"),
])
def test_dodaj_uzytkownika_ok_param(core_tmp, ids, login, haslo, rola):
    core_tmp.dodaj_uzytkownika(login, haslo, rola, kod_odzyskiwania="KOD", budynek_id=ids["budynek_id"])
    u = core_tmp.pobierz_uzytkownika_po_loginie(login)
    assert u and u[1] == login and u[2] == haslo and u[3] == rola

@pytest.mark.parametrize("login,haslo", [("", "x"), ("x","")])
def test_dodaj_uzytkownika_brak_login_haslo(core_tmp, login, haslo):
    with pytest.raises(ValueError):
        core_tmp.dodaj_uzytkownika(login, haslo, "PRACOWNIK")

@pytest.mark.parametrize("rola", ["", "HACKER", "USER", None])
def test_dodaj_uzytkownika_zla_rola(core_tmp, rola):
    with pytest.raises(ValueError):
        core_tmp.dodaj_uzytkownika("X", "Y", rola)

def test_dodaj_uzytkownika_duplikat(core_tmp):
    with pytest.raises(ValueError):
        core_tmp.dodaj_uzytkownika("Pracownik", "xxx", "PRACOWNIK")

def test_lista_uzytkownikow_sort_i_zawartosc(core_tmp):
    rows = core_tmp.lista_uzytkownikow()
    loginy = [r[1] for r in rows]
    assert "Admin" in loginy and "Pracownik" in loginy and "Technik" in loginy
    assert loginy == sorted(loginy)  # sort po loginie

@pytest.mark.parametrize("newpass", ["1", "haslo", "1234567890"])
def test_ustaw_haslo_ok(core_tmp, newpass):
    assert core_tmp.ustaw_haslo("Pracownik", newpass) is True
    u = core_tmp.pobierz_uzytkownika_po_loginie("Pracownik")
    assert u[2] == newpass

@pytest.mark.parametrize("badpass", ["", None])
def test_ustaw_haslo_puste(core_tmp, badpass):
    assert core_tmp.ustaw_haslo("Pracownik", badpass) is False

@pytest.mark.parametrize("token", ["TOKEN123", "A"*32, "x_y-z"])
def test_ustaw_token_reset_ok(core_tmp, token):
    assert core_tmp.ustaw_token_reset("Pracownik", token) is True
    u = core_tmp.pobierz_uzytkownika_po_loginie("Pracownik")
    assert u[4] == token

@pytest.mark.parametrize("token", ["", None])
def test_ustaw_token_reset_pusty(core_tmp, token):
    assert core_tmp.ustaw_token_reset("Pracownik", token) is False

def test_ustaw_login_haslo_duplikat_login(core_tmp):
    u = core_tmp.pobierz_uzytkownika_po_loginie("Technik")
    with pytest.raises(ValueError):
        core_tmp.ustaw_login_haslo_dla_uzytkownika(u[0], "Admin")

def test_usun_uzytkownika(core_tmp):
    core_tmp.dodaj_uzytkownika("DoSkasowania", "x", "PRACOWNIK")
    u = core_tmp.pobierz_uzytkownika_po_loginie("DoSkasowania")
    core_tmp.usun_uzytkownika(u[0])
    assert core_tmp.pobierz_uzytkownika_po_loginie("DoSkasowania") is None
