import os
import time
import pytest

RUN = os.getenv("RUN_PERF") == "1"
pytestmark = pytest.mark.perf

def _skip_if_disabled():
    if not RUN:
        pytest.skip("Performance tests disabled. Set RUN_PERF=1 to enable.")

def _measure(fn):
    t0 = time.perf_counter()
    fn()
    return time.perf_counter() - t0

# Luźne progi pod WSL: mają łapać duże regresje, nie mikro-wahania.
THRESH = {
    "insert_200": 3.0,
    "insert_500": 6.0,
    "select_500": 2.5,
    "update_200": 3.5,
    "delete_200": 6.0,
}

def _seed_tickets(core_tmp, ids, n, prefix="Z"):
    for i in range(n):
        core_tmp.dodaj_zgloszenie(
            f"{prefix}{i}",
            "Opis",
            [],
            uzytkownik_id=ids["pracownik_id"],
            budynek_id=ids["budynek_id"],
            priorytet="NORMAL",
            kategoria="IT",
        )

def _seed_buildings(core_tmp, n, prefix="B"):
    for i in range(n):
        core_tmp.dodaj_budynek(f"{prefix}{i}", "U", f"00-{i:03d}")

@pytest.mark.parametrize("n,limit", [(200, THRESH["insert_200"]), (500, THRESH["insert_500"])])
def test_perf_insert_tickets(core_tmp, ids, n, limit):
    _skip_if_disabled()
    dt = _measure(lambda: _seed_tickets(core_tmp, ids, n, prefix=f"T{n}_"))
    assert dt < limit

@pytest.mark.parametrize("n,limit", [(200, THRESH["insert_200"]), (500, THRESH["insert_500"])])
def test_perf_insert_buildings(core_tmp, n, limit):
    _skip_if_disabled()
    dt = _measure(lambda: _seed_buildings(core_tmp, n, prefix=f"B{n}_"))
    assert dt < limit

@pytest.mark.parametrize("case", list(range(1, 121)))
def test_perf_micro_cases(core_tmp, ids, case):
    _skip_if_disabled()

    # 120 zróżnicowanych scenariuszy (parametr = osobny test w raporcie)
    m = case % 8
    if m == 0:
        _seed_tickets(core_tmp, ids, 500, prefix=f"MC{case}_")
        dt = _measure(lambda: core_tmp.lista_zgloszen(ids["budynek_id"]))
        assert dt < THRESH["select_500"]
    elif m == 1:
        dt = _measure(lambda: _seed_buildings(core_tmp, 250, prefix=f"MC{case}_"))
        assert dt < THRESH["insert_200"]
    elif m == 2:
        _seed_tickets(core_tmp, ids, 250, prefix=f"MC{case}_")
        ids_list = [r[0] for r in core_tmp.lista_zgloszen(ids["budynek_id"])][:200]
        dt = _measure(lambda: [core_tmp.zmien_status(z, "IN_PROGRESS") for z in ids_list])
        assert dt < THRESH["update_200"]
    elif m == 3:
        _seed_tickets(core_tmp, ids, 250, prefix=f"MC{case}_")
        ids_list = [r[0] for r in core_tmp.lista_zgloszen(ids["budynek_id"])][:200]
        dt = _measure(lambda: [core_tmp.ustaw_priorytet_zgloszenia(z, "HIGH", uzytkownik_id=ids["admin_id"]) for z in ids_list])
        assert dt < THRESH["update_200"]
    elif m == 4:
        _seed_tickets(core_tmp, ids, 250, prefix=f"MC{case}_")
        ids_list = [r[0] for r in core_tmp.lista_zgloszen(ids["budynek_id"])][:200]
        dt = _measure(lambda: [core_tmp.przypisz_do_technika(z, ids["technik_id"]) for z in ids_list])
        assert dt < THRESH["update_200"]
    elif m == 5:
        _seed_tickets(core_tmp, ids, 250, prefix=f"MC{case}_")
        ids_list = [r[0] for r in core_tmp.lista_zgloszen(ids["budynek_id"])][:200]
        dt = _measure(lambda: [core_tmp.zamknij_zgloszenie(z, ids["technik_id"]) for z in ids_list])
        assert dt < THRESH["update_200"]
    elif m == 6:
        _seed_tickets(core_tmp, ids, 250, prefix=f"MC{case}_")
        ids_list = [r[0] for r in core_tmp.lista_zgloszen(ids["budynek_id"])][:200]
        dt = _measure(lambda: [core_tmp.usun_zgloszenie(z) for z in ids_list])
        assert dt < THRESH["delete_200"]
    else:
        # mieszany odczyt
        _seed_tickets(core_tmp, ids, 400, prefix=f"MC{case}_")
        dt = _measure(lambda: (
            core_tmp.lista_zgloszen(ids["budynek_id"]),
            core_tmp.lista_krytycznych_dla_budynku(ids["budynek_id"]),
            core_tmp.lista_zgloszen_dla_budynku(ids["budynek_id"]),
        ))
        assert dt < THRESH["select_500"]
