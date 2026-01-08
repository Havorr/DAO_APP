import pathlib
import pytest

@pytest.fixture()
def core_tmp(tmp_path, monkeypatch):
    """Izoluje bazę i folder zdjęć dla core.py (bez GUI)."""
    import core as core_mod

    db_path = tmp_path / "zgloszenia.db"
    photos_dir = tmp_path / "zdjecia"
    photos_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(core_mod, "BAZA_DANYCH", str(db_path), raising=False)
    monkeypatch.setattr(core_mod, "FOLDER_ZDJEC", str(photos_dir), raising=False)

    core_mod.inicjalizuj_baze()
    return core_mod

@pytest.fixture()
def ids(core_tmp):
    prac = core_tmp.pobierz_uzytkownika_po_loginie("Pracownik")
    tech = core_tmp.pobierz_uzytkownika_po_loginie("Technik")
    adm = core_tmp.pobierz_uzytkownika_po_loginie("Admin")
    assert prac and tech and adm
    bud_id = prac[5]
    assert bud_id is not None
    return {
        "pracownik_id": prac[0],
        "technik_id": tech[0],
        "admin_id": adm[0],
        "budynek_id": bud_id,
    }

def _make_dummy_file(path: pathlib.Path, content: bytes = b"X"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return str(path)

@pytest.fixture()
def dummy_photo(tmp_path):
    p = tmp_path / "input_photo.png"
    return _make_dummy_file(p, b"fakepng")

@pytest.fixture()
def many_files(tmp_path):
    files = []
    for i in range(40):
        p = tmp_path / f"f{i}.bin"
        p.write_bytes(b"x" * 10)
        files.append(str(p))
    return files
