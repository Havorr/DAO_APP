# core.py – logika aplikacji i baza danych
import os
import sys
import sqlite3
import datetime
import shutil
import sqlite3


# -------------------- Ścieżki --------------------
def katalog_bazowy():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


KATALOG = katalog_bazowy()
BAZA_DANYCH = os.path.join(KATALOG, "zgloszenia.db")
FOLDER_ZDJEC = os.path.join(KATALOG, "zdjecia")

os.makedirs(FOLDER_ZDJEC, exist_ok=True)

# -------------------- Stałe / słowniki --------------------
STATUSY = ["OPEN", "IN_PROGRESS", "DONE"]

DOZWOLONE = {
    "OPEN": {"OPEN", "IN_PROGRESS", "DONE"},
    "IN_PROGRESS": {"IN_PROGRESS", "DONE"},
    "DONE": {"DONE"},
}

ROLE = ["PRACOWNIK", "TECHNIK", "ADMIN"]

# priorytety i kategorie dla zgłoszeń
PRIORYTETY = ["LOW", "NORMAL", "HIGH", "CRITICAL"]
KATEGORIE = ["Elektryka", "Woda", "HVAC", "IT", "P.poż", "Inne"]

# typy okresowych przeglądów technicznych
PRZEGLADY_TYPY = [
    "GAZ",
    "KOMINIARSKI",
    "ELEKTRYCZNA",
    "WINDA",
    "PPOZ",
    "KANALIZACJA",
]

PRZEGLADY_NAZWY = {
    "GAZ": "Instalacja gazowa",
    "KOMINIARSKI": "Przegląd kominiarski",
    "ELEKTRYCZNA": "Instalacja elektryczna",
    "WINDA": "Winda",
    "PPOZ": "P.pożar",
    "KANALIZACJA": "Instalacja kanalizacyjna",
}
# odwrotne mapowanie: z nazwy wyświetlanej na kod techniczny
PRZEGLADY_NAZWY_ODWROTNIE = {v: k for k, v in PRZEGLADY_NAZWY.items()}


# -------------------- Narzędzia ogólne --------------------
def teraz_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def polacz():
    conn = sqlite3.connect(BAZA_DANYCH)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def inicjalizuj_baze():
    with polacz() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS zgloszenia
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tytul TEXT NOT NULL,
                opis TEXT,
                status TEXT NOT NULL CHECK (
                    status IN ('OPEN','IN_PROGRESS','DONE')
                ),
                utworzono TEXT NOT NULL,
                zaktualizowano TEXT NOT NULL,
                uzytkownik_id INTEGER,
                budynek_id INTEGER,
                priorytet TEXT NOT NULL DEFAULT 'NORMAL',
                kategoria TEXT,
                przypisany_technik_id INTEGER,
                zamkniete_przez INTEGER
            );

            CREATE TABLE IF NOT EXISTS zdjecia
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zgloszenie_id INTEGER NOT NULL,
                sciezka TEXT NOT NULL,
                FOREIGN KEY (zgloszenie_id) REFERENCES zgloszenia(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS uzytkownicy
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                login TEXT UNIQUE NOT NULL,
                haslo TEXT NOT NULL,
                rola TEXT NOT NULL CHECK (
                    rola IN ('PRACOWNIK','TECHNIK','ADMIN')
                )
            );

            CREATE TABLE IF NOT EXISTS budynki
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nazwa TEXT NOT NULL UNIQUE,
                ulica TEXT NOT NULL,
                kod_pocztowy TEXT NOT NULL,
                stan TEXT NOT NULL,
                opis TEXT NOT NULL,
                liczba_pieter INTEGER NOT NULL DEFAULT 10,
                liczba_wind INTEGER NOT NULL DEFAULT 2,
                wyjscia_na_pietro INTEGER NOT NULL DEFAULT 2
            );

            CREATE TABLE IF NOT EXISTS zgloszenia_logi
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zgloszenie_id INTEGER NOT NULL,
                uzytkownik_id INTEGER,
                czas TEXT NOT NULL,
                typ TEXT NOT NULL,
                szczegoly TEXT,
                FOREIGN KEY (zgloszenie_id) REFERENCES zgloszenia(id) ON DELETE CASCADE,
                FOREIGN KEY (uzytkownik_id) REFERENCES uzytkownicy(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS przeglady_techniczne
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                budynek_id INTEGER NOT NULL,
                typ TEXT NOT NULL,
                data_wizyty TEXT NOT NULL,
                technik TEXT NOT NULL,
                uwagi TEXT,
                FOREIGN KEY (budynek_id) REFERENCES budynki(id) ON DELETE CASCADE
            );

        """)

        c.commit()

        cur = c.cursor()

        # --- tabela powiązań użytkownik <-> budynek (wiele do wielu) ---
        cur.execute("""
            CREATE TABLE IF NOT EXISTS uzytkownicy_budynki (
                uzytkownik_id INTEGER NOT NULL,
                budynek_id    INTEGER NOT NULL,
                PRIMARY KEY (uzytkownik_id, budynek_id),
                FOREIGN KEY (uzytkownik_id) REFERENCES uzytkownicy(id) ON DELETE CASCADE,
                FOREIGN KEY (budynek_id)    REFERENCES budynki(id)      ON DELETE CASCADE
            )
        """)
        c.commit()

        # --- uzytkownicy: dodaj brakujące kolumny (dla starych baz) ---
        cur.execute("PRAGMA table_info(uzytkownicy)")
        kolumny_u = [row[1] for row in cur.fetchall()]
        if "kod_odzyskiwania" not in kolumny_u:
            cur.execute("ALTER TABLE uzytkownicy ADD COLUMN kod_odzyskiwania TEXT")
        if "budynek_id" not in kolumny_u:
            cur.execute("ALTER TABLE uzytkownicy ADD COLUMN budynek_id INTEGER")
        if "ostatnie_logowanie" not in kolumny_u:
            # przechowujemy datę ostatniego logowania w formacie ISO
            cur.execute("ALTER TABLE uzytkownicy ADD COLUMN ostatnie_logowanie TEXT")
        c.commit()

        # --- migracja starego pola uzytkownicy.budynek_id -> tabela powiązań ---
        # (w tym miejscu kolumna budynek_id już istnieje)
        cur.execute("""
            INSERT OR IGNORE INTO uzytkownicy_budynki(uzytkownik_id, budynek_id)
            SELECT u.id, u.budynek_id
            FROM uzytkownicy u
            JOIN budynki b ON b.id = u.budynek_id
            WHERE u.budynek_id IS NOT NULL
        """)
        c.commit()

        # --- zgloszenia: upewnij się, że są nowe kolumny ---
        cur.execute("PRAGMA table_info(zgloszenia)")
        kolumny_z = [row[1] for row in cur.fetchall()]
        if "uzytkownik_id" not in kolumny_z:
            cur.execute("ALTER TABLE zgloszenia ADD COLUMN uzytkownik_id INTEGER")
        if "budynek_id" not in kolumny_z:
            cur.execute("ALTER TABLE zgloszenia ADD COLUMN budynek_id INTEGER")
        if "priorytet" not in kolumny_z:
            cur.execute("ALTER TABLE zgloszenia ADD COLUMN priorytet TEXT DEFAULT 'NORMAL'")
        if "kategoria" not in kolumny_z:
            cur.execute("ALTER TABLE zgloszenia ADD COLUMN kategoria TEXT")
        if "przypisany_technik_id" not in kolumny_z:
            cur.execute("ALTER TABLE zgloszenia ADD COLUMN przypisany_technik_id INTEGER")
        if "zamkniete_przez" not in kolumny_z:
            cur.execute("ALTER TABLE zgloszenia ADD COLUMN zamkniete_przez INTEGER")
        c.commit()

        # --- budynki: upewnij się, że są nowe kolumny techniczne ---
        cur.execute("PRAGMA table_info(budynki)")
        kolumny_b = [row[1] for row in cur.fetchall()]
        if "liczba_pieter" not in kolumny_b:
            cur.execute(
                "ALTER TABLE budynki "
                "ADD COLUMN liczba_pieter INTEGER NOT NULL DEFAULT 10"
            )
        if "liczba_wind" not in kolumny_b:
            cur.execute(
                "ALTER TABLE budynki "
                "ADD COLUMN liczba_wind INTEGER NOT NULL DEFAULT 2"
            )
        if "wyjscia_na_pietro" not in kolumny_b:
            cur.execute(
                "ALTER TABLE budynki "
                "ADD COLUMN wyjscia_na_pietro INTEGER NOT NULL DEFAULT 2"
            )
        c.commit()

        # --- domyślny budynek dla Pracownika ---
        cur.execute("""
            SELECT id FROM budynki
            WHERE nazwa=? AND ulica=? AND kod_pocztowy=?
        """, ("Warszawa", "Al. Jerozolimskie 220A", "02-495"))
        row = cur.fetchone()
        if row:
            bud_id = row[0]
        else:
            cur.execute("""
                INSERT INTO budynki(nazwa, ulica, kod_pocztowy, stan, opis)
                VALUES(?,?,?,?,?)
            """, (
                "Warszawa",
                "Al. Jerozolimskie 220A",
                "02-495",
                "Sprawny",
                "Brak aktywnych krytycznych usterek."
            ))
            bud_id = cur.lastrowid
        c.commit()

        # ---- Tworzenie / uzupełnianie kont startowych ----
        def ensure_user(login, haslo, rola, kod, budynek_id=None):
            cur.execute("SELECT id FROM uzytkownicy WHERE login=?", (login,))
            existing = cur.fetchone()
            if not existing:
                # tworzymy nowego użytkownika (tu ustawiamy domyślny budynek tylko przy pierwszym razie)
                cur.execute(
                    """
                    INSERT INTO uzytkownicy(login, haslo, rola, kod_odzyskiwania, budynek_id)
                    VALUES(?,?,?,?,?)
                    """,
                    (login, haslo, rola, kod, budynek_id),
                )
            else:
                # użytkownik istnieje – uzupełniamy TYLKO kod_odzyskiwania
                cur.execute(
                    """
                    UPDATE uzytkownicy
                    SET kod_odzyskiwania = COALESCE(kod_odzyskiwania, ?)
                    WHERE login = ?
                    """,
                    (kod, login),
                )


        ensure_user("Pracownik", "123", "PRACOWNIK", "4mfs12XSq4S_", bud_id)
        ensure_user("Technik", "321", "TECHNIK", "h8Pq92LmZ1x_", None)
        ensure_user("Admin", "qaz", "ADMIN", "A9sQ77nBx2L_", None)

        # --- indeksy przyspieszające zapytania ---
        cur.executescript("""
            CREATE INDEX IF NOT EXISTS idx_zgloszenia_budynek
                ON zgloszenia(budynek_id);
            CREATE INDEX IF NOT EXISTS idx_zgloszenia_status
                ON zgloszenia(status);
            CREATE INDEX IF NOT EXISTS idx_zdjecia_zgloszenie
                ON zdjecia(zgloszenie_id);
            CREATE INDEX IF NOT EXISTS idx_logi_zgloszenie
                ON zgloszenia_logi(zgloszenie_id);
            CREATE INDEX IF NOT EXISTS idx_przeglady_budynek_typ
                ON przeglady_techniczne(budynek_id, typ);
        """)

        c.commit()


def ustaw_rozmiar_okna_procent(okno, width_frac=0.7, height_frac=0.7, min_frac=0.5):
    """
    Ustawia rozmiar okna jako procent rozdzielczości ekranu
    i nadaje minimalny rozmiar (min_frac ekranu).
    """
    okno.update_idletasks()

    sw = okno.winfo_screenwidth()
    sh = okno.winfo_screenheight()

    w = int(sw * width_frac)
    h = int(sh * height_frac)
    min_w = int(sw * min_frac)
    min_h = int(sh * min_frac)

    # minimalny rozmiar (co najmniej połowa ekranu, jeśli min_frac=0.5)
    okno.minsize(min_w, min_h)

    # wyśrodkowanie
    x = (sw - w) // 2
    y = (sh - h) // 2
    okno.geometry(f"{w}x{h}+{x}+{y}")


# -------------------- Funkcje dotyczące zgłoszeń --------------------
def dodaj_zgloszenie(tytul, opis, sciezki, uzytkownik_id=None, budynek_id=None,
                     priorytet="NORMAL", kategoria=None):
    tytul = (tytul or "").strip()
    if not tytul:
        raise ValueError("Tytuł jest wymagany.")
    teraz = teraz_iso()
    priorytet = priorytet or "NORMAL"
    with polacz() as c:
        cur = c.cursor()
        cur.execute("""
            INSERT INTO zgloszenia(
                tytul, opis, status, utworzono, zaktualizowano,
                uzytkownik_id, budynek_id, priorytet, kategoria,
                przypisany_technik_id, zamkniete_przez
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """, (
            tytul,
            (opis or "").strip(),
            "OPEN",
            teraz,
            teraz,
            uzytkownik_id,
            budynek_id,
            priorytet,
            kategoria,
            None,
            None,
        ))
        zgl_id = cur.lastrowid
        for plik in sciezki or []:
            nazwa = os.path.basename(plik)
            cel = os.path.join(FOLDER_ZDJEC, f"{zgl_id}_{nazwa}")
            shutil.copy2(plik, cel)
            cur.execute(
                "INSERT INTO zdjecia(zgloszenie_id, sciezka) VALUES(?,?)",
                (zgl_id, cel),
            )
        c.commit()

    # log utworzenia zgłoszenia
    if uzytkownik_id:
        try:
            dodaj_log(zgl_id, uzytkownik_id, "CREATE", f"Utworzono zgłoszenie: {tytul}")
        except Exception:
            # logi są pomocnicze – nie blokujemy aplikacji, jeśli coś nie wyjdzie
            pass


def lista_zgloszen(budynek_id=None):
    """Lista zgłoszeń do zakładki 'Lista zgłoszeń'.

    Odporna na brak kolumn priorytet/kategoria (stare bazy).

    Jeśli budynek_id jest podane, zwracane są tylko zgłoszenia
    przypisane do tego budynku.
    """
    with polacz() as c:
        cur = c.cursor()

        # sprawdzamy jakie kolumny ma tabela
        cur.execute("PRAGMA table_info(zgloszenia)")
        kolumny = [row[1] for row in cur.fetchall()]
        has_priorytet = "priorytet" in kolumny
        has_kategoria = "kategoria" in kolumny

        select_sql = """
            SELECT
                z.id,
                z.tytul,
                z.status,
        """

        if has_priorytet:
            select_sql += " z.priorytet AS priorytet, "
        else:
            select_sql += " 'NORMAL' AS priorytet, "

        if has_kategoria:
            select_sql += " COALESCE(z.kategoria, '') AS kategoria, "
        else:
            select_sql += " '' AS kategoria, "

        select_sql += """
                (SELECT COUNT(1) FROM zdjecia s WHERE s.zgloszenie_id = z.id) AS zdjecia,
                z.utworzono,
                z.zaktualizowano
            FROM zgloszenia z
        """

        if budynek_id is not None:
            select_sql += """
            WHERE z.budynek_id = ?
            """

        select_sql += """
            ORDER BY z.utworzono DESC
        """

        if budynek_id is not None:
            cur.execute(select_sql, (budynek_id,))
        else:
            cur.execute(select_sql)

        return cur.fetchall()


def lista_zgloszen_z_budynkiem():
    """Lista zgłoszeń z nazwą budynku (dla widoku ADMIN)."""
    with polacz() as c:
        cur = c.cursor()

        # sprawdzamy jakie kolumny ma tabela
        cur.execute("PRAGMA table_info(zgloszenia)")
        kolumny = [row[1] for row in cur.fetchall()]
        has_priorytet = "priorytet" in kolumny
        has_kategoria = "kategoria" in kolumny

        select_sql = """
            SELECT
                z.id,
                z.tytul,
                z.status,
        """

        if has_priorytet:
            select_sql += " z.priorytet AS priorytet, "
        else:
            select_sql += " 'NORMAL' AS priorytet, "

        if has_kategoria:
            select_sql += " COALESCE(z.kategoria, '') AS kategoria, "
        else:
            select_sql += " '' AS kategoria, "

        select_sql += """
                (SELECT COUNT(1) FROM zdjecia s WHERE s.zgloszenie_id = z.id) AS zdjecia,
                z.utworzono,
                z.zaktualizowano,
                COALESCE(b.nazwa, '') AS budynek
            FROM zgloszenia z
            LEFT JOIN budynki b ON b.id = z.budynek_id
            ORDER BY z.utworzono DESC
        """

        cur.execute(select_sql)
        return cur.fetchall()


def lista_zgloszen_dla_budynku(budynek_id, limit=20):
    with polacz() as c:
        cur = c.cursor()
        cur.execute("""
            SELECT id, tytul, status, utworzono, zaktualizowano
            FROM zgloszenia
            WHERE budynek_id=?
            ORDER BY utworzono DESC
            LIMIT ?
        """, (budynek_id, limit))
        return cur.fetchall()


def lista_krytycznych_dla_budynku(budynek_id):
    """Zwraca listę ID zgłoszeń o priorytecie CRITICAL dla danego budynku,
    które nie są zakończone (status != 'DONE')."""
    with polacz() as c:
        cur = c.cursor()
        cur.execute("""
            SELECT id
            FROM zgloszenia
            WHERE budynek_id = ?
              AND priorytet = 'CRITICAL'
              AND status != 'DONE'
            ORDER BY utworzono DESC
        """, (budynek_id,))
        return cur.fetchall()


def lista_przegladow_dla_budynku(budynek_id):
    """
    Zwraca listę przeglądów technicznych dla danego budynku.
    Wynik: lista krotek (typ, data_wizyty, technik, uwagi),
    posortowana malejąco po dacie wizyty (najnowsze na górze).
    """
    with polacz() as c:
        cur = c.cursor()
        cur.execute("""
            SELECT typ, data_wizyty, technik, COALESCE(uwagi, '')
            FROM przeglady_techniczne
            WHERE budynek_id = ?
            ORDER BY data_wizyty DESC, id DESC
        """, (budynek_id,))
        return cur.fetchall()


def ostatnie_przeglady_dla_budynku(budynek_id):
    """
    Zwraca listę ostatnich przeglądów dla każdego typu z PRZEGLADY_TYPY.
    Wynik: [(typ, data_ostatniego, data_koniec_waznosci, technik), ...]
    Jeśli dla typu nie ma żadnego wpisu w bazie – daty/technik są None.
    """
    with polacz() as c:
        cur = c.cursor()
        cur.execute("""
            SELECT typ, data_wizyty, technik
            FROM przeglady_techniczne
            WHERE budynek_id = ?
            ORDER BY data_wizyty DESC, id DESC
        """, (budynek_id,))
        rows = cur.fetchall()

    # wybieramy najnowszy wpis dla każdego typu
    ostatnie = {}
    for typ, data_wizyty, technik in rows:
        if typ not in ostatnie:
            ostatnie[typ] = (data_wizyty, technik)

    wynik = []
    for typ in PRZEGLADY_TYPY:
        data_wizyty, technik = ostatnie.get(typ, (None, None))
        if data_wizyty:
            # data końca ważności = + 1 rok
            try:
                d = datetime.datetime.fromisoformat(data_wizyty[:10]).date()
                try:
                    d_koniec = d.replace(year=d.year + 1)
                except ValueError:
                    # np. 29.02 – awaryjnie +365 dni
                    d_koniec = d + datetime.timedelta(days=365)
                data_koniec = d_koniec.strftime("%Y-%m-%d")
            except Exception:
                data_koniec = None
        else:
            data_koniec = None
        wynik.append((typ, data_wizyty, data_koniec, technik))

    return wynik


def historia_przegladow_dla_budynku_i_typu(budynek_id, typ):
    """
    Historia przeglądów danego typu dla budynku.
    Wynik: lista krotek (id, data_wizyty, technik, uwagi),
    najnowsze na górze.
    """
    with polacz() as c:
        cur = c.cursor()
        cur.execute(
            """
            SELECT id, data_wizyty, technik, COALESCE(uwagi, '')
            FROM przeglady_techniczne
            WHERE budynek_id = ? AND typ = ?
            ORDER BY data_wizyty DESC, id DESC
            """,
            (budynek_id, typ),
        )
        return cur.fetchall()



def dodaj_przeglad_techniczny(budynek_id, typ, data_wizyty, technik, uwagi=None):
    """
    Dodaje nowy przegląd techniczny do bazy.
    """
    if not budynek_id:
        raise ValueError("Brak przypisanego budynku.")
    typ = (typ or "").strip()
    data_wizyty = (data_wizyty or "").strip()
    technik = (technik or "").strip()
    if not typ or not data_wizyty or not technik:
        raise ValueError("Typ, data wizyty i technik są wymagane.")
    with polacz() as c:
        cur = c.cursor()
        cur.execute("""
            INSERT INTO przeglady_techniczne(budynek_id, typ, data_wizyty, technik, uwagi)
            VALUES(?,?,?,?,?)
        """, (budynek_id, typ, data_wizyty, technik, uwagi))
        c.commit()


def edytuj_przeglad_techniczny(przeglad_id, data_wizyty, technik, uwagi=None):
    """
    Aktualizuje istniejący przegląd techniczny.
    Zwraca True, jeśli coś zostało zmienione.
    """
    if not data_wizyty or not technik:
        raise ValueError("Data wizyty i technik są wymagane.")

    data_wizyty = (data_wizyty or "").strip()
    technik = (technik or "").strip()
    uwagi = (uwagi or "").strip() or None

    with polacz() as c:
        cur = c.cursor()
        cur.execute(
            """
            UPDATE przeglady_techniczne
            SET data_wizyty = ?, technik = ?, uwagi = ?
            WHERE id = ?
            """,
            (data_wizyty, technik, uwagi, przeglad_id),
        )
        c.commit()
        return cur.rowcount > 0


def usun_przeglad_techniczny(przeglad_id):
    """
    Usuwa przegląd techniczny o podanym ID.
    Zwraca True, jeśli wpis został usunięty.
    """
    with polacz() as c:
        cur = c.cursor()
        cur.execute(
            "DELETE FROM przeglady_techniczne WHERE id = ?",
            (przeglad_id,),
        )
        c.commit()
        return cur.rowcount > 0



def pobierz_zgloszenie(zgl_id):
    with polacz() as c:
        cur = c.cursor()
        z = cur.execute("SELECT * FROM zgloszenia WHERE id=?", (zgl_id,)).fetchone()
        if not z:
            return None, []
        zdj = cur.execute("SELECT id, sciezka FROM zdjecia WHERE zgloszenie_id=? ORDER BY id", (zgl_id,)).fetchall()
        return z, zdj


def zmien_status(zgl_id, nowy):
    if nowy not in STATUSY:
        return False
    with polacz() as c:
        cur = c.cursor()
        cur.execute("SELECT status FROM zgloszenia WHERE id=?", (zgl_id,))
        row = cur.fetchone()
        if not row:
            return False
        obecny = row[0]
        if nowy not in DOZWOLONE[obecny]:
            return False
        cur.execute("UPDATE zgloszenia SET status=?, zaktualizowano=? WHERE id=?", (nowy, teraz_iso(), zgl_id))
        c.commit()
        return True


def ustaw_priorytet_zgloszenia(zgl_id, priorytet, uzytkownik_id=None):
    """
    Ustawia priorytet zgłoszenia + aktualizuje 'zaktualizowano'
    i dopisuje log CHANGE_PRIORITY.
    """
    priorytet = (priorytet or "NORMAL").strip()
    if priorytet not in PRIORYTETY:
        return False

    with polacz() as c:
        cur = c.cursor()
        cur.execute(
            "UPDATE zgloszenia SET priorytet=?, zaktualizowano=? WHERE id=?",
            (priorytet, teraz_iso(), zgl_id),
        )
        c.commit()
        ok = cur.rowcount > 0

    # log tylko jeśli update się powiódł i mamy ID użytkownika
    if ok and uzytkownik_id is not None:
        try:
            dodaj_log(
                zgl_id,
                uzytkownik_id,
                "CHANGE_PRIORITY",
                f"Zmieniono priorytet na {priorytet}.",
            )
        except Exception:
            # log nie jest krytyczny dla działania aplikacji
            pass

    return ok


def usun_zgloszenie(zgl_id):
    with polacz() as c:
        cur = c.cursor()
        zdj = cur.execute("SELECT sciezka FROM zdjecia WHERE zgloszenie_id=?", (zgl_id,)).fetchall()
        for (sciezka,) in zdj:
            if os.path.exists(sciezka):
                try:
                    os.remove(sciezka)
                except OSError:
                    pass
        cur.execute("DELETE FROM zgloszenia WHERE id=?", (zgl_id,))
        c.commit()


# -------------------- Modyfikacja zgłoszeń --------------------

def ustaw_opis_zgloszenia(zgloszenie_id, nowy_opis, uzytkownik_id=None):
    """Aktualizacja opisu zgłoszenia + log."""
    with polacz() as c:
        cur = c.cursor()
        cur.execute(
            "UPDATE zgloszenia SET opis=?, zaktualizowano=? WHERE id=?",
            ((nowy_opis or "").strip(), teraz_iso(), zgloszenie_id),
        )
        c.commit()
    if uzytkownik_id:
        try:
            dodaj_log(
                zgloszenie_id,
                uzytkownik_id,
                "EDIT_DESCRIPTION",
                "Zmieniono opis zgłoszenia.",
            )
        except Exception:
            pass


def dodaj_zdjecia_do_zgloszenia(zgloszenie_id, pliki, uzytkownik_id=None):
    """Dodaje nowe zdjęcia do istniejącego zgłoszenia + log."""
    if not pliki:
        return
    with polacz() as c:
        cur = c.cursor()
        for sciezka in pliki:
            nazwa = os.path.basename(sciezka)
            cel = os.path.join(FOLDER_ZDJEC, f"{zgloszenie_id}_{nazwa}")
            shutil.copy2(sciezka, cel)
            cur.execute(
                "INSERT INTO zdjecia(zgloszenie_id, sciezka) VALUES(?,?)",
                (zgloszenie_id, cel),
            )
        c.commit()
    if uzytkownik_id:
        try:
            dodaj_log(
                zgloszenie_id,
                uzytkownik_id,
                "ADD_PHOTOS",
                "Dodano zdjęcia do zgłoszenia.",
            )
        except Exception:
            pass


def usun_zdjecie_ze_zgloszenia(zgloszenie_id, sciezka, uzytkownik_id=None):
    """Usuwa jedno zdjęcie ze zgłoszenia + log."""
    # najpierw usuwamy rekord z bazy
    with polacz() as c:
        cur = c.cursor()
        cur.execute(
            "DELETE FROM zdjecia WHERE zgloszenie_id = ? AND sciezka = ?",
            (zgloszenie_id, sciezka),
        )
        c.commit()

    # potem próbujemy usunąć plik z dysku
    try:
        if os.path.exists(sciezka):
            os.remove(sciezka)
    except Exception:
        # nie przerywamy z tego powodu całej operacji
        pass

    if uzytkownik_id:
        try:
            dodaj_log(
                zgloszenie_id,
                uzytkownik_id,
                "DELETE_PHOTO",
                f"Usunięto zdjęcie: {os.path.basename(sciezka)}",
            )
        except Exception:
            pass


def zamknij_zgloszenie(zgloszenie_id, technik_id):
    """
    Automatycznie zamyka zgłoszenie:
    - status -> DONE (Zamknięty)
    - zapisuje, który technik je zamknął
    """
    with polacz() as c:
        cur = c.cursor()
        # jeśli już zamknięte – nic nie rób
        cur.execute("SELECT status FROM zgloszenia WHERE id=?", (zgloszenie_id,))
        row = cur.fetchone()
        if not row or row[0] == "DONE":
            return False

        cur.execute(
            """
            UPDATE zgloszenia
            SET status = 'DONE',
                zamkniete_przez = ?,
                zaktualizowano = ?
            WHERE id = ?
            """,
            (technik_id, teraz_iso(), zgloszenie_id),
        )
        c.commit()

    try:
        dodaj_log(
            zgloszenie_id,
            technik_id,
            "CLOSE",
            "Zgłoszenie zamknięte przez technika.",
        )
    except Exception:
        pass

    return True


# -------------------- Logi zgłoszeń --------------------


def dodaj_log(zgloszenie_id, uzytkownik_id, typ, szczegoly):
    """Zapisuje zmianę w historii zgłoszenia."""
    with polacz() as c:
        cur = c.cursor()
        cur.execute("""
            INSERT INTO zgloszenia_logi(zgloszenie_id, uzytkownik_id, czas, typ, szczegoly)
            VALUES(?,?,?,?,?)
        """, (zgloszenie_id, uzytkownik_id, teraz_iso(), typ, (szczegoly or "")))
        c.commit()


def pobierz_logi(zgloszenie_id, rola="PRACOWNIK"):
    """
    Zwraca logi dla zgłoszenia.
    - Pracownik nie widzi komentarzy wewnętrznych.
    - Treść komentarzy (publicznych i wewnętrznych) NIE jest pokazywana w historii,
      tylko informacja, że dodano komentarz.
    """
    with polacz() as c:
        cur = c.cursor()

        sql = """
            SELECT l.czas,
                   COALESCE(u.login, '(brak)') AS login,
                   l.typ,
                   l.szczegoly
            FROM zgloszenia_logi l
            LEFT JOIN uzytkownicy u ON l.uzytkownik_id = u.id
            WHERE l.zgloszenie_id = ?
        """
        params = [zgloszenie_id]

        if rola == "PRACOWNIK":
            sql += " AND l.typ != 'COMMENT_INTERNAL'"

        sql += " ORDER BY l.czas"

        cur.execute(sql, params)
        rows = cur.fetchall()

    wyniki = []
    for czas, login, typ, szczegoly in rows:
        if typ == "COMMENT_PUBLIC":
            szczegoly = "Dodano komentarz publiczny."
        elif typ == "COMMENT_INTERNAL":
            szczegoly = "Dodano notatkę wewnętrzną."
        wyniki.append((czas, login, typ, szczegoly))
    return wyniki


def przypisz_do_technika(zgloszenie_id, technik_id, force_reopen=False):
    """
    Przypisuje zgłoszenie do technika.

    Jeśli force_reopen == True (używane przez ADMINA),
    to status zawsze ustawiany jest na IN_PROGRESS,
    nawet gdy wcześniej było DONE.
    """
    with polacz() as c:
        cur = c.cursor()

        if force_reopen:
            # ADMIN może „odkleić” DONE -> IN_PROGRESS
            cur.execute(
                """
                UPDATE zgloszenia
                SET przypisany_technik_id = ?,
                    zaktualizowano = ?,
                    status = 'IN_PROGRESS'
                WHERE id = ?
                """,
                (technik_id, teraz_iso(), zgloszenie_id),
            )
        else:
            # dotychczasowe zachowanie
            cur.execute(
                """
                UPDATE zgloszenia
                SET przypisany_technik_id = ?,
                    zaktualizowano = ?,
                    status = CASE
                        WHEN status = 'DONE' THEN status
                        ELSE 'IN_PROGRESS'
                    END
                WHERE id = ?
                """,
                (technik_id, teraz_iso(), zgloszenie_id),
            )

        c.commit()
        return cur.rowcount > 0


def pobierz_przypisanego_technika(zgloszenie_id):
    with polacz() as c:
        cur = c.cursor()
        row = cur.execute("""
            SELECT u.login
            FROM zgloszenia z
            LEFT JOIN uzytkownicy u ON z.przypisany_technik_id = u.id
            WHERE z.id = ?
        """, (zgloszenie_id,)).fetchone()
        return row[0] if row else None


# -------------------- Funkcje dotyczące użytkowników i budynków --------------------
def dodaj_uzytkownika(login, haslo, rola, kod_odzyskiwania=None, budynek_id=None):
    login = (login or "").strip()
    if not login or not haslo:
        raise ValueError("Login i hasło są wymagane.")
    if rola not in ROLE:
        raise ValueError("Nieprawidłowa rola użytkownika.")
    with polacz() as c:
        cur = c.cursor()
        try:
            cur.execute("""
                INSERT INTO uzytkownicy(login, haslo, rola, kod_odzyskiwania, budynek_id)
                VALUES(?,?,?,?,?)
            """, (login, haslo, rola, kod_odzyskiwania, budynek_id))
            c.commit()
        except sqlite3.IntegrityError:
            raise ValueError("Użytkownik o takim loginie już istnieje.")


def usun_uzytkownika(uzytkownik_id):
    """Usuwa użytkownika o podanym ID."""
    with polacz() as c:
        cur = c.cursor()
        cur.execute("DELETE FROM uzytkownicy WHERE id=?", (uzytkownik_id,))
        c.commit()


def lista_uzytkownikow():
    with polacz() as c:
        cur = c.cursor()
        cur.execute("SELECT id, login, rola FROM uzytkownicy ORDER BY login")
        return cur.fetchall()


def pobierz_uzytkownika_po_loginie(login):
    with polacz() as c:
        cur = c.cursor()
        return cur.execute(
            "SELECT id, login, haslo, rola, kod_odzyskiwania, budynek_id "
            "FROM uzytkownicy WHERE login=?",
            (login,)
        ).fetchone()


def ustaw_haslo(login, nowe_haslo):
    if not nowe_haslo:
        return False
    with polacz() as c:
        cur = c.cursor()
        cur.execute("UPDATE uzytkownicy SET haslo=? WHERE login=?", (nowe_haslo, login))
        c.commit()
        return cur.rowcount > 0


def ustaw_token_reset(login, nowy_token):
    """Ustawia nowy token (kod_odzyskiwania) dla podanego loginu."""
    if not nowy_token:
        return False
    with polacz() as c:
        cur = c.cursor()
        cur.execute(
            "UPDATE uzytkownicy SET kod_odzyskiwania=? WHERE login=?",
            (nowy_token, login),
        )
        c.commit()
        return cur.rowcount > 0


def ustaw_login_haslo_dla_uzytkownika(uzytkownik_id, nowy_login, nowe_haslo=None):
    """
    Zmienia login (i opcjonalnie hasło) dla użytkownika o danym ID.
    Rzuca ValueError jeśli login już istnieje.
    """
    nowy_login = (nowy_login or "").strip()
    if not nowy_login:
        raise ValueError("Login nie może być pusty.")

    with polacz() as c:
        cur = c.cursor()

        # sprawdź czy login nie jest zajęty przez innego użytkownika
        cur.execute(
            "SELECT id FROM uzytkownicy WHERE login=? AND id<>?",
            (nowy_login, uzytkownik_id),
        )
        if cur.fetchone():
            raise ValueError("Użytkownik o takim loginie już istnieje.")

        if nowe_haslo:
            cur.execute(
                "UPDATE uzytkownicy SET login=?, haslo=? WHERE id=?",
                (nowy_login, nowe_haslo, uzytkownik_id),
            )
        else:
            cur.execute(
                "UPDATE uzytkownicy SET login=? WHERE id=?",
                (nowy_login, uzytkownik_id),
            )
        c.commit()
        return cur.rowcount > 0


def usun_budynek(budynek_id):
    """
    Usuwa budynek:
    - odczepia powiązane zgłoszenia (budynek_id = NULL)
    - kasuje rekord z tabeli budynki
    Powiązania w uzytkownicy_budynki usuwają się przez ON DELETE CASCADE.
    """
    with polacz() as c:
        cur = c.cursor()
        # zgłoszenia tracą przypisanie do budynku
        cur.execute(
            "UPDATE zgloszenia SET budynek_id=NULL WHERE budynek_id=?",
            (budynek_id,),
        )
        # usuwamy sam budynek
        cur.execute("DELETE FROM budynki WHERE id=?", (budynek_id,))
        c.commit()


def lista_budynkow_dla_uzytkownika(uzytkownik_id):
    """
    Zwraca listę budynków przypisanych do użytkownika:
    [(id, nazwa), ...]
    Dla ADMINA zwraca automatycznie WSZYSTKIE budynki.
    """
    with polacz() as c:
        cur = c.cursor()
        # sprawdzamy rolę
        cur.execute("SELECT rola FROM uzytkownicy WHERE id=?", (uzytkownik_id,))
        row = cur.fetchone()
        if not row:
            return []
        rola = row[0]

        # ADMIN -> automatycznie wszystkie budynki
        if rola == "ADMIN":
            cur.execute("SELECT id, nazwa FROM budynki ORDER BY nazwa")
            return cur.fetchall()

        # inni -> z tabeli powiązań
        cur.execute("""
            SELECT b.id, b.nazwa
            FROM uzytkownicy_budynki ub
            JOIN budynki b ON b.id = ub.budynek_id
            WHERE ub.uzytkownik_id = ?
            ORDER BY b.nazwa
        """, (uzytkownik_id,))
        return cur.fetchall()


def ustaw_budynki_dla_uzytkownika(uzytkownik_id, budynki_ids):
    """
    Nadpisuje przypisane budynki użytkownika.
    - kasuje stare powiązania z uzytkownicy_budynki
    - dodaje nowe
    - aktualizuje kolumnę uzytkownicy.budynek_id na "domyślny" (pierwszy z listy)
    """
    budynki_ids = [int(b) for b in (budynki_ids or [])]
    # usuwamy duplikaty z zachowaniem kolejności
    budynki_ids = list(dict.fromkeys(budynki_ids))

    with polacz() as c:
        cur = c.cursor()

        # czy to admin? – dla admina nic nie zapisujemy, ma wszystkie z automatu
        cur.execute("SELECT rola FROM uzytkownicy WHERE id=?", (uzytkownik_id,))
        row = cur.fetchone()
        if not row:
            return
        rola = row[0]
        if rola == "ADMIN":
            # ADMIN ma wszystkie budynki logicznie, nie musimy nic wstawiać
            return

        # kasujemy stare powiązania
        cur.execute(
            "DELETE FROM uzytkownicy_budynki WHERE uzytkownik_id=?",
            (uzytkownik_id,)
        )

        # dodajemy nowe
        for bid in budynki_ids:
            cur.execute(
                "INSERT OR IGNORE INTO uzytkownicy_budynki(uzytkownik_id, budynek_id) VALUES(?,?)",
                (uzytkownik_id, bid),
            )

        # ustawiamy domyślny budynek w starej kolumnie
        if budynki_ids:
            cur.execute(
                "UPDATE uzytkownicy SET budynek_id=? WHERE id=?",
                (budynki_ids[0], uzytkownik_id),
            )
        else:
            cur.execute(
                "UPDATE uzytkownicy SET budynek_id=NULL WHERE id=?",
                (uzytkownik_id,),
            )

        c.commit()


def pobierz_budynek_dla_uzytkownika(uzytkownik_id):
    """
    Zwraca "domyślny" budynek użytkownika jako słownik:
    {
        id, nazwa, ulica, kod_pocztowy, stan, opis,
        liczba_pieter, liczba_wind, wyjscia_na_pietro
    }

    - ADMIN -> pierwszy budynek z tabeli budynki (ma dostęp do wszystkich)
    - inni -> najpierw uzytkownicy.budynek_id,
              jeśli puste, to pierwszy z uzytkownicy_budynki
    """
    with polacz() as c:
        cur = c.cursor()

        # najpierw pobieramy rolę i ew. budynek_id z tabeli uzytkownicy
        cur.execute(
            "SELECT rola, budynek_id FROM uzytkownicy WHERE id=?",
            (uzytkownik_id,),
        )
        row_u = cur.fetchone()
        if not row_u:
            return None

        rola, bud_id = row_u[0], row_u[1]
        row = None

        if rola == "ADMIN":
            # admin – pierwszy budynek z listy (ale logika dostępu: wszystkie)
            row = cur.execute("""
                SELECT
                    b.id,
                    b.nazwa,
                    b.ulica,
                    b.kod_pocztowy,
                    b.stan,
                    b.opis,
                    COALESCE(b.liczba_pieter, 10),
                    COALESCE(b.liczba_wind, 2),
                    COALESCE(b.wyjscia_na_pietro, 2)
                FROM budynki b
                ORDER BY b.id
                LIMIT 1
            """).fetchone()
        else:
            if bud_id is not None:
                row = cur.execute("""
                    SELECT
                        b.id,
                        b.nazwa,
                        b.ulica,
                        b.kod_pocztowy,
                        b.stan,
                        b.opis,
                        COALESCE(b.liczba_pieter, 10),
                        COALESCE(b.liczba_wind, 2),
                        COALESCE(b.wyjscia_na_pietro, 2)
                    FROM budynki b
                    WHERE b.id=?
                """, (bud_id,)).fetchone()

            # jeśli nie ma ustawionego budynek_id – bierzemy pierwszy z powiązań
            if row is None:
                row = cur.execute("""
                    SELECT
                        b.id,
                        b.nazwa,
                        b.ulica,
                        b.kod_pocztowy,
                        b.stan,
                        b.opis,
                        COALESCE(b.liczba_pieter, 10),
                        COALESCE(b.liczba_wind, 2),
                        COALESCE(b.wyjscia_na_pietro, 2)
                    FROM uzytkownicy_budynki ub
                    JOIN budynki b ON b.id = ub.budynek_id
                    WHERE ub.uzytkownik_id=?
                    ORDER BY b.id
                    LIMIT 1
                """, (uzytkownik_id,)).fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "nazwa": row[1],
            "ulica": row[2],
            "kod_pocztowy": row[3],
            "stan": row[4],
            "opis": row[5],
            "liczba_pieter": row[6],
            "liczba_wind": row[7],
            "wyjscia_na_pietro": row[8],
        }


def lista_budynkow():
    """Lista wszystkich budynków (id, nazwa) – do comboboxa w zakładce kont."""
    with polacz() as c:
        cur = c.cursor()
        cur.execute("SELECT id, nazwa FROM budynki ORDER BY nazwa")
        return cur.fetchall()


def dodaj_budynek(
    nazwa,
    ulica="",
    kod_pocztowy="",
    stan="",
    opis="",
    liczba_pieter=10,
    liczba_wind=2,
    wyjscia_na_pietro=2,
):
    """
    Dodaje nowy budynek do bazy i zwraca jego ID.
    Używane w panelu admina.
    """
    nazwa = (nazwa or "").strip()
    if not nazwa:
        raise ValueError("Nazwa budynku jest wymagana.")

    try:
        with polacz() as c:
            cur = c.cursor()
            cur.execute(
                """
                INSERT INTO budynki(
                    nazwa,
                    ulica,
                    kod_pocztowy,
                    stan,
                    opis,
                    liczba_pieter,
                    liczba_wind,
                    wyjscia_na_pietro
                )
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    nazwa,
                    ulica or "",
                    kod_pocztowy or "",
                    stan or "",
                    opis or "",
                    int(liczba_pieter),
                    int(liczba_wind),
                    int(wyjscia_na_pietro),
                ),
            )
            c.commit()
            return cur.lastrowid

    except sqlite3.IntegrityError as e:
        # np. UNIQUE constraint failed: budynki.nazwa
        raise ValueError("Budynek o takiej nazwie już istnieje.") from e
def pobierz_budynek_po_id(budynek_id: int | None):
    """
    Zwraca budynek o podanym ID jako słownik w takiej samej formie,
    jak pobierz_budynek_dla_uzytkownika().
    """
    if budynek_id is None:
        return None

    with polacz() as c:
        cur = c.cursor()
        row = cur.execute(
            """
            SELECT b.id,
                   b.nazwa,
                   b.ulica,
                   b.kod_pocztowy,
                   b.stan,
                   b.opis,
                   COALESCE(b.liczba_pieter, 10),
                   COALESCE(b.liczba_wind, 2),
                   COALESCE(b.wyjscia_na_pietro, 2)
            FROM budynki b
            WHERE b.id = ?
            """,
            (budynek_id,),
        ).fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "nazwa": row[1],
        "ulica": row[2],
        "kod_pocztowy": row[3],
        "stan": row[4],
        "opis": row[5],
        "liczba_pieter": row[6],
        "liczba_wind": row[7],
        "wyjscia_na_pietro": row[8],
    }


def edytuj_budynek(
        budynek_id,
        nazwa,
        ulica="",
        kod_pocztowy="",
        stan="",
        opis="",
        liczba_pieter=10,
        liczba_wind=2,
        wyjscia_na_pietro=2,
):
    """
    Aktualizuje dane istniejącego budynku.
    Używane w oknie 'Edytuj budynek'.
    """
    nazwa = (nazwa or "").strip()
    if not nazwa:
        raise ValueError("Nazwa budynku jest wymagana.")

    with polacz() as c:
        cur = c.cursor()
        try:
            cur.execute(
                """
                UPDATE budynki
                SET
                    nazwa = ?,
                    ulica = ?,
                    kod_pocztowy = ?,
                    stan = ?,
                    opis = ?,
                    liczba_pieter = ?,
                    liczba_wind = ?,
                    wyjscia_na_pietro = ?
                WHERE id = ?
                """,
                (
                    nazwa,
                    ulica or "",
                    kod_pocztowy or "",
                    stan or "",
                    opis or "",
                    int(liczba_pieter),
                    int(liczba_wind),
                    int(wyjscia_na_pietro),
                    budynek_id,
                ),
            )
            c.commit()
        except sqlite3.IntegrityError:
            # nazwa w tabeli budynki jest UNIQUE – ładny komunikat zamiast crusha
            raise ValueError("Budynek o takiej nazwie już istnieje.")


def lista_uzytkownikow_szczegoly():
    """
    Zwraca szczegółową listę kont do zakładki admina.

    Każdy wiersz:
    (id, login, haslo, rola, nazwa_budynku, budynek_id, ostatnie_logowanie)
    """
    with polacz() as c:
        cur = c.cursor()
        cur.execute(
            """
            SELECT
                u.id,
                u.login,
                u.haslo,
                u.rola,
                COALESCE(b.nazwa, '(brak)') AS budynek,
                u.budynek_id,
                u.ostatnie_logowanie
            FROM uzytkownicy u
            LEFT JOIN budynki b ON u.budynek_id = b.id
            ORDER BY u.login
            """
        )
        return cur.fetchall()


def ustaw_budynek_dla_uzytkownika(uzytkownik_id, budynek_id):
    """Zmienia przypisany budynek (może być None)."""
    with polacz() as c:
        cur = c.cursor()
        cur.execute(
            "UPDATE uzytkownicy SET budynek_id=? WHERE id=?",
            (budynek_id, uzytkownik_id),
        )
        c.commit()
        return cur.rowcount > 0