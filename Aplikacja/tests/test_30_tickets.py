import pytest

def test_dodaj_zgloszenie_wymaga_tytulu(core_tmp):
    with pytest.raises(ValueError):
        core_tmp.dodaj_zgloszenie("", "opis", [])
