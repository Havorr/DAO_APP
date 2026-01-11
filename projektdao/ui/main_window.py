import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from ui.theme import get_colors, set_theme, get_theme, apply_entry_style
import datetime
import random
import string

from core import (
    ustaw_rozmiar_okna_procent,
    pobierz_budynek_dla_uzytkownika,
    pobierz_budynek_po_id,
    lista_zgloszen,
    lista_zgloszen_z_budynkiem,
    lista_przegladow_dla_budynku,
    lista_zgloszen_dla_budynku,
    lista_krytycznych_dla_budynku,
    lista_uzytkownikow,
    lista_uzytkownikow_szczegoly,
    lista_budynkow,
    lista_budynkow_dla_uzytkownika,
    ustaw_budynki_dla_uzytkownika,
    dodaj_zgloszenie,
    dodaj_przeglad_techniczny,
    ostatnie_przeglady_dla_budynku,
    historia_przegladow_dla_budynku_i_typu,
    edytuj_przeglad_techniczny,
    usun_przeglad_techniczny,
    dodaj_budynek,
    edytuj_budynek,
    usun_budynek,
    ustaw_budynek_dla_uzytkownika,
    dodaj_uzytkownika,
    ustaw_login_haslo_dla_uzytkownika,
    usun_uzytkownika,
    ustaw_haslo,
    STATUSY,
    KATEGORIE,
    PRIORYTETY,
    PRZEGLADY_TYPY,
    PRZEGLADY_NAZWY,
    PRZEGLADY_NAZWY_ODWROTNIE,
    pobierz_zgloszenie,
    dodaj_log,
    pobierz_logi,
    dodaj_zdjecia_do_zgloszenia,
    usun_zdjecie_ze_zgloszenia,
    zamknij_zgloszenie,
    usun_zgloszenie,
    pobierz_uzytkownika_po_loginie,
    ustaw_token_reset,
    teraz_iso,
)
from ui.details import SzczegolyOkno


# -------------------- Interfejs GUI główny --------------------
class Exception:
    pass


class Aplikacja(tk.Tk):
    def __init__(self, uzytkownik):
        super().__init__()

        # najpierw ustawiamy styl pól (mamy już self)
        apply_entry_style(self)

        # potem pobieramy kolory motywu
        colors = get_colors()

        # rozmiar w procentach ekranu: ~80%, min. 50%
        ustaw_rozmiar_okna_procent(self, width_frac=0.8, height_frac=0.8, min_frac=0.5)
        self.resizable(True, True)

        self.uzytkownik = uzytkownik  # dict: id, login, rola, budynek_id
        self._after_symul = None
        self._after_czas = None
        self.chce_wylogowac = False
        self.budynek = pobierz_budynek_dla_uzytkownika(self.uzytkownik["id"])

        # lista budynków dostępnych dla użytkownika (dla ADMINA – wszystkie)
        self.budynki_dostepne = lista_budynkow_dla_uzytkownika(self.uzytkownik["id"])

        # pomocnicze rzeczy do przełączania budynku
        self.budynek_var = None          # StringVar dla comboboxa
        self.budynek_id_map = {}         # nazwa -> id
        self.przeglady_naglowek = None   # LabelFrame z nagłówkiem przeglądów


        tyt = (
            "System Zgłoszeń Usterek - Urząd Gminy "
            f"(zalogowano: {self.uzytkownik['login']} / {self.uzytkownik['rola']})"
        )
        self.title(tyt)
        self.sciezki_zdjec = []

        # REFERENCJA DO OKNA SZCZEGÓŁÓW
        self.okno_szczegoly = None

        # Okienka ADMINA – tylko jedna instancja każdego typu
        self.okno_dodaj_budynek = None
        self.okno_usun_budynek = None
        self.okno_edytuj_budynek = None
        self.okno_edycja_konta = None
        self.okno_historia_przegladu = None

        # motyw (jasny / ciemny) – startowy zgodny z theme.py
        self.tryb_ciemny = (get_theme() == "dark")

        # referencje do widżetów pulpitu
        self.tabela_powiad = None
        self.tabela_przeglady = None
        self.tabela_wyjsc = None
        self.lbl_net = None
        self.lbl_elev1 = None
        self.lbl_elev2 = None
        self.lbl_elevators = []   # lista etykiet dla każdej windy
        self.lbl_power = None
        self.lbl_water = None
        self.lbl_budynek_stan = None  # NOWE
        self.lbl_budynek_opis = None  # (jeśli jeszcze nie masz – dodaj)
        self.lbl_wyjscia_podsum = None
        self.wyjscia = []  # lista (pietro, nazwa)
        self._wyjscia_status = {}  # pamięć stanu i czasu zmiany dla każdego wyjścia

        # paski czasu i sesji
        self.lbl_czas_globalny = None
        self.lbl_czas_sesji = None
        self.session_start = datetime.datetime.now()  # początek sesji

        # stan wind (symulacja ruchu) – dynamicznie, wg liczby wind z bazy
        # każdy element listy to słownik z parametrami jednej windy
        self.elevators = []

        # ile wind deklaruje budynek (domyślnie 2)
        liczba_wind = 2
        if self.budynek:
            try:
                liczba_wind = int(self.budynek.get("liczba_wind", 2))
            except (TypeError, ValueError):
                liczba_wind = 2

        # mały bezpiecznik – nie przesadzamy z liczbą
        liczba_wind = max(1, min(liczba_wind, 10))

        for i in range(liczba_wind):
            # startowe piętra możesz sobie później zmienić wg uznania
            start_floor = 0 if i == 0 else i * 2
            self.elevators.append(
                {
                    "floor": start_floor,
                    "target": start_floor,
                    "dir": 0,       # -1 w dół, 0 stoi, 1 w górę
                    "speed": 0.0,   # m/s
                    "wait": 0,      # ile "tików" jeszcze stoi na piętrze
                }
            )


        # budujemy GUI dopiero teraz
        self._buduj_gui()
        self.odswiez_liste()
        self.odswiez_pulpit()
        self.odswiez_przeglady()

        # start symulatorów i zegara (po zbudowaniu etykiet!)
        self._start_symulatory()
        self._aktualizuj_czas()

    # ---------- GUI ----------
    def _buduj_gui(self):
        # GŁÓWNY KONTENER – margines od krawędzi okna
        root = ttk.Frame(self, padding=(16, 12, 16, 16))
        root.pack(fill="both", expand=True)

        # ========== GÓRNY PASEK / NAGŁÓWEK ==========
        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 8))

        # Ikona po lewej
        lbl_icon = ttk.Label(
            header,
            text="🛠",
            font=("Segoe UI", 20, "bold"),
        )
        lbl_icon.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 10))

        # Tytuł aplikacji
        lbl_title = ttk.Label(
            header,
            text="System zgłoszeń usterek",
            font=("Segoe UI", 14, "bold"),
        )
        lbl_title.grid(row=0, column=1, sticky="w", pady=(0, 2))

        # Podtytuł
        lbl_subtitle = ttk.Label(
            header,
            text="Panel pracownika Urzędu Gminy",
            font=("Segoe UI", 9),
        )
        lbl_subtitle.grid(row=1, column=1, sticky="w")

        # Prawa część nagłówka – zegary, użytkownik, Wyloguj
        right = ttk.Frame(header)
        right.grid(row=0, column=2, rowspan=2, sticky="e")

        # Zegar globalny
        self.lbl_czas_globalny = ttk.Label(right, text="Czas (Warszawa): -")
        self.lbl_czas_globalny.grid(row=0, column=0, sticky="e", padx=(0, 8))

        # Czas trwania sesji
        self.lbl_czas_sesji = ttk.Label(right, text="Sesja: 00:00:00")
        self.lbl_czas_sesji.grid(row=1, column=0, sticky="e", padx=(0, 8), pady=(2, 0))

        # Informacja o zalogowanym użytkowniku
        user_txt = f"{self.uzytkownik['login']} ({self.uzytkownik['rola']})"
        self.lbl_user = ttk.Label(right, text=user_txt)
        self.lbl_user.grid(row=0, column=1, rowspan=2, sticky="e", padx=(0, 8))

        # Przycisk „Wyloguj”
        btn_wyloguj = ttk.Button(right, text="Wyloguj", command=self._wyloguj)
        btn_wyloguj.grid(row=0, column=2, rowspan=2, sticky="e")

        # Środkowa kolumna nagłówka ma się rozciągać
        header.columnconfigure(1, weight=1)

        # Cienka linia pod nagłówkiem
        ttk.Separator(root, orient="horizontal").pack(fill="x", pady=(4, 8))

        # ========== OBSZAR ZAKŁADEK ==========
        notebook_container = ttk.Frame(root)
        notebook_container.pack(fill="both", expand=True)

        karty = ttk.Notebook(notebook_container)
        karty.pack(fill="both", expand=True)
        self.karty = karty

        # --- Pulpit + przeglądy dla PRACOWNIK ---
        if self.uzytkownik["rola"] == "PRACOWNIK":
            self.karta_pulpit = ttk.Frame(karty)
            karty.add(self.karta_pulpit, text="Pulpit")
            self._buduj_pulpit_pracownika(self.karta_pulpit)

            self.karta_przeglady = ttk.Frame(karty)
            karty.add(self.karta_przeglady, text="Przeglądy techniczne")
            self._buduj_przeglady_techniczne(self.karta_przeglady)

        # --- Pulpit + przeglądy dla TECHNIK (z możliwością dodawania) ---
        elif self.uzytkownik["rola"] == "TECHNIK":
            self.karta_pulpit = ttk.Frame(karty)
            karty.add(self.karta_pulpit, text="Pulpit")
            self._buduj_pulpit_pracownika(self.karta_pulpit)

            self.karta_przeglady = ttk.Frame(karty)
            karty.add(self.karta_przeglady, text="Przeglądy techniczne")
            self._buduj_przeglady_techniczne_admin(self.karta_przeglady)

        # --- Przeglądy dla ADMIN (z możliwością dodawania) ---
        elif self.uzytkownik["rola"] == "ADMIN":
            self.karta_przeglady = ttk.Frame(karty)
            karty.add(self.karta_przeglady, text="Przeglądy techniczne")
            self._buduj_przeglady_techniczne_admin(self.karta_przeglady)

        # --- Karta nowego zgłoszenia ---

        self.karta_nowe = ttk.Frame(karty)
        karty.add(self.karta_nowe, text="Nowe zgłoszenie")
        frm_nowe = ttk.LabelFrame(self.karta_nowe, text="Formularz nowego zgłoszenia")
        frm_nowe.pack(fill="both", expand=True, padx=10, pady=10)


        # ===== WYBÓR BUDYNKU (tylko ADMIN) =====

        self.zgl_budynek_var = None

        self.zgl_budynek_id_map = {}

        first_row = 0  # od którego wiersza zaczynają się pola tytułu/opisu

        if self.uzytkownik.get("rola") == "ADMIN":

            self.zgl_budynek_var = tk.StringVar()

            self.zgl_budynek_id_map = {}

            budynki_admina = lista_budynkow_dla_uzytkownika(self.uzytkownik["id"])

            nazwy_budynkow = []

            for bid, nazwa in budynki_admina:
                nazwy_budynkow.append(nazwa)

                self.zgl_budynek_id_map[nazwa] = bid

            ttk.Label(frm_nowe, text="Budynek:").grid(

                row=0, column=0, sticky="w", padx=8, pady=4

            )

            self.zgl_budynek_combo = ttk.Combobox(

                frm_nowe,

                textvariable=self.zgl_budynek_var,

                values=nazwy_budynkow,

                state="readonly",

                width=40,

            )

            self.zgl_budynek_combo.grid(

                row=0, column=1, sticky="we", padx=8, pady=4

            )

            if nazwy_budynkow:
                self.zgl_budynek_var.set(nazwy_budynkow[0])

            # jeśli jest pole "Budynek", resztę pól przesuwamy o 1 w dół

            first_row = 1

        # ===== Tytuł zgłoszenia =====

        ttk.Label(frm_nowe, text="Tytuł zgłoszenia:").grid(

            row=first_row, column=0, sticky="w", padx=8, pady=6

        )

        self.tytul_entry = ttk.Entry(frm_nowe, width=70, style="Dark.TEntry")

        self.tytul_entry.grid(row=first_row, column=1, sticky="we", padx=8, pady=6)

        # ===== Opis usterki =====

        ttk.Label(frm_nowe, text="Opis usterki:").grid(

            row=first_row + 1, column=0, sticky="nw", padx=8, pady=6

        )

        colors = get_colors()

        self.opis_text = tk.Text(

            frm_nowe,

            height=8,

            wrap="word",

            bg=colors["input_bg"],

            fg=colors["text"],

            insertbackground=colors["text"],  # kolor kursora

            relief="flat",

            highlightthickness=1,

            highlightbackground=colors["input_border"],

        )

        self.opis_text.grid(

            row=first_row + 1, column=1, sticky="nsew", padx=8, pady=6

        )

        # ===== Kategoria =====

        ttk.Label(frm_nowe, text="Kategoria:").grid(

            row=first_row + 2, column=0, sticky="w", padx=8, pady=4

        )

        self.kategoria_var = tk.StringVar(value=KATEGORIE[0])

        self.kategoria_combo = ttk.Combobox(

            frm_nowe,

            textvariable=self.kategoria_var,

            values=KATEGORIE,

            state="readonly",

            width=20,

        )

        self.kategoria_combo.grid(

            row=first_row + 2, column=1, sticky="w", padx=8, pady=4

        )

        # ===== Zdjęcia =====

        ttk.Button(

            frm_nowe, text="Dodaj zdjęcia", command=self._wybierz_zdjecia

        ).grid(row=first_row + 3, column=1, sticky="w", padx=8, pady=4)

        self.label_zdjecia = ttk.Label(frm_nowe, text="Brak wybranych plików")

        self.label_zdjecia.grid(

            row=first_row + 4, column=1, sticky="w", padx=8, pady=(0, 6)

        )

        # ===== Zapis =====

        ttk.Button(

            frm_nowe, text="Zapisz zgłoszenie", command=self._zapisz_zgloszenie

        ).grid(row=first_row + 5, column=1, sticky="e", padx=8, pady=8)

        frm_nowe.columnconfigure(1, weight=1)

        frm_nowe.rowconfigure(first_row + 1, weight=1)

        # --- Karta lista zgłoszeń ---
        self.karta_lista = ttk.Frame(karty)
        karty.add(self.karta_lista, text="Lista zgłoszeń")

        filtry = ttk.LabelFrame(self.karta_lista, text="Filtry")
        filtry.pack(fill="x", padx=8, pady=(8, 4))

        self.filter_status_var = tk.StringVar(value="(wszystkie)")
        self.filter_priorytet_var = tk.StringVar(value="(wszystkie)")
        self.filter_kategoria_var = tk.StringVar(value="(wszystkie)")
        self.filter_tytul_var = tk.StringVar(value="")
        self.filter_id_var = tk.StringVar(value="")
        self.filter_data_kolumna_var = tk.StringVar(value="(brak)")
        self.filter_data_od_var = tk.StringVar(value="")
        self.filter_data_do_var = tk.StringVar(value="")

        if self.uzytkownik.get("rola") == "ADMIN":
            self.filter_budynek_var = tk.StringVar(value="")

        ttk.Label(filtry, text="Status:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.filter_status_combo = ttk.Combobox(
            filtry,
            textvariable=self.filter_status_var,
            values=["(wszystkie)"] + STATUSY,
            state="readonly",
            width=12,
        )
        self.filter_status_combo.grid(row=0, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(filtry, text="Priorytet:").grid(row=0, column=2, sticky="w", padx=4, pady=2)
        self.filter_priorytet_combo = ttk.Combobox(
            filtry,
            textvariable=self.filter_priorytet_var,
            values=["(wszystkie)"] + PRIORYTETY,
            state="readonly",
            width=12,
        )
        self.filter_priorytet_combo.grid(row=0, column=3, sticky="w", padx=4, pady=2)

        ttk.Label(filtry, text="Kategoria:").grid(row=0, column=4, sticky="w", padx=4, pady=2)
        self.filter_kategoria_combo = ttk.Combobox(
            filtry,
            textvariable=self.filter_kategoria_var,
            values=["(wszystkie)"] + KATEGORIE,
            state="readonly",
            width=14,
        )
        self.filter_kategoria_combo.grid(row=0, column=5, sticky="w", padx=4, pady=2)

        # --- panel przycisków pod filtrami (lista zgłoszeń) ---
        panel_lista = ttk.Frame(self.karta_lista)
        panel_lista.pack(fill="x", padx=8, pady=(0, 4))

        btn_odswiez = ttk.Button(
            panel_lista,
            text="Odśwież",
            command=self.odswiez_liste,
        )
        btn_odswiez.pack(side="left", padx=4, pady=2)

        btn_wyczysc = ttk.Button(
            panel_lista,
            text="Wyczyść filtry",
            command=self._wyczysc_filtry,
        )
        btn_wyczysc.pack(side="left", padx=4, pady=2)

        # --- tabela zgłoszeń ---
        tabela_frame = ttk.Frame(self.karta_lista)
        tabela_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # kolumny – ADMIN widzi dodatkowo budynek
        if self.uzytkownik.get("rola") == "ADMIN":
            kolumny = (
                "ID",
                "Tytuł",
                "Status",
                "Priorytet",
                "Kategoria",
                "Zdjęcia",
                "Utworzono",
                "Zaktualizowano",
                "Budynek",
            )
        else:
            kolumny = (
                "ID",
                "Tytuł",
                "Status",
                "Priorytet",
                "Kategoria",
                "Zdjęcia",
                "Utworzono",
                "Zaktualizowano",
            )

        self.tabela = ttk.Treeview(
            tabela_frame,
            columns=kolumny,
            show="headings",
            height=14,
        )
        self.tabela.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(
            tabela_frame,
            orient="vertical",
            command=self.tabela.yview,
        )
        scrollbar.pack(side="right", fill="y")
        self.tabela.configure(yscrollcommand=scrollbar.set)

        # mapowanie nazw kolumn na indeksy w krotce r z bazy
        self._map_kolumn_index = {
            "ID": 0,
            "Tytuł": 1,
            "Status": 2,
            "Priorytet": 3,
            "Kategoria": 4,
            "Zdjęcia": 5,
            "Utworzono": 6,
            "Zaktualizowano": 7,
        }
        if "Budynek" in kolumny:
            self._map_kolumn_index["Budynek"] = 8

        # stan sortowania listy zgłoszeń
        self._sort_column = None
        self._sort_order = None
        self._wszystkie_zgloszenia = []

        # nagłówki + podpinamy sortowanie dla wybranych kolumn
        for k in kolumny:
            if k in ("ID", "Tytuł", "Zdjęcia", "Utworzono", "Zaktualizowano", "Budynek"):
                self.tabela.heading(
                    k,
                    text=k,
                    command=lambda c=k: self._klik_naglowek_listy(c),
                )
            else:
                self.tabela.heading(k, text=k)

        # szerokości kolumn
        self.tabela.column("ID", width=60, anchor="center")
        self.tabela.column("Tytuł", width=260, anchor="w")
        self.tabela.column("Status", width=110, anchor="center")
        self.tabela.column("Priorytet", width=90, anchor="center")
        self.tabela.column("Kategoria", width=110, anchor="center")
        self.tabela.column("Zdjęcia", width=70, anchor="center")
        self.tabela.column("Utworzono", width=140, anchor="center")
        self.tabela.column("Zaktualizowano", width=140, anchor="center")
        if "Budynek" in kolumny:
            self.tabela.column("Budynek", width=220, anchor="w")

        # dwuklik w wiersz -> okno szczegółów zgłoszenia
        self.tabela.bind("<Double-1>", self._pokaz_szczegoly)

        # --- jeśli użytkownik to ADMIN – karta kont użytkowników ---
        if self.uzytkownik["rola"] == "ADMIN":
            self.karta_konta = ttk.Frame(karty)
            karty.add(self.karta_konta, text="Konta użytkowników")
            self._buduj_konta_uzytkownikow(self.karta_konta)

        # --- Zakładka ustawień (dla wszystkich użytkowników) ---
        self.karta_ustawienia = ttk.Frame(karty)
        karty.add(self.karta_ustawienia, text="Ustawienia")
        self._buduj_ustawienia(self.karta_ustawienia)


        # Na koniec zastosuj aktualny motyw (jasny/ciemny)
        self._zastosuj_motyw()

    def _wycentruj_okno(self, okno):
        """
        Wyśrodkowuje podane okno Toplevel względem głównego okna aplikacji,
        nie zmieniając jego rozmiaru.
        """
        okno.update_idletasks()

        # aktualny (lub wymagany) rozmiar okna podrzędnego
        w = okno.winfo_width()
        h = okno.winfo_height()
        if w <= 1 or h <= 1:
            # gdy okno jest jeszcze "1x1", użyj wymaganego rozmiaru
            w = okno.winfo_reqwidth()
            h = okno.winfo_reqheight()

        # pozycja i rozmiar głównego okna
        self.update_idletasks()
        x_root = self.winfo_x()
        y_root = self.winfo_y()
        w_root = self.winfo_width()
        h_root = self.winfo_height()

        x = x_root + (w_root - w) // 2
        y = y_root + (h_root - h) // 2

        # Uwaga: NIE podajemy w,h – zostają takie, jakie policzył Tkinter
        okno.geometry(f"+{x}+{y}")

    def _buduj_pulpit_pracownika(self, frame):
        # ---- Informacje o budynku + monitoring w jednym wierszu ----
        if not self.budynek:
            ttk.Label(
                frame,
                text="Brak przypisanego budynku do tego użytkownika.",
            ).pack(anchor="w", padx=10, pady=10)
            return

        # górny wiersz – dwa bloki obok siebie
        top_row = ttk.Frame(frame)
        top_row.pack(fill="x", padx=10, pady=10)

        # ---- Informacje o budynku ----
        info = ttk.LabelFrame(top_row, text="Informacje o budynku")
        info.pack(side="left", fill="both", expand=True, padx=(0, 5))

        ttk.Label(info, text=f"Nazwa: {self.budynek['nazwa']}").pack(
            anchor="w", padx=8, pady=2
        )
        ttk.Label(info, text=f"Adres: {self.budynek['ulica']}").pack(
            anchor="w", padx=8, pady=2
        )
        ttk.Label(info, text=f"Kod pocztowy: {self.budynek['kod_pocztowy']}").pack(
            anchor="w", padx=8, pady=2
        )

        # nowe informacje stałe o budynku
        try:
            lp = int(self.budynek.get("liczba_pieter", 0))
            lw = int(self.budynek.get("liczba_wind", 0))
            wyj = int(self.budynek.get("wyjscia_na_pietro", 0))
        except (TypeError, ValueError):
            lp = lw = wyj = 0

        if lp:
            ttk.Label(info, text=f"Liczba pięter: {lp}").pack(
                anchor="w", padx=8, pady=2
            )
        if lw:
            ttk.Label(info, text=f"Liczba wind: {lw}").pack(
                anchor="w", padx=8, pady=2
            )
        if wyj:
            ttk.Label(info, text=f"Wyjścia ewakuacyjne/p.poż na piętro: {wyj}").pack(
                anchor="w", padx=8, pady=2
            )

        # dynamiczny stan budynku – będzie ustawiany w _odswiez_opis_krytyczne
        self.lbl_budynek_stan = ttk.Label(info, text="Stan: -")
        self.lbl_budynek_stan.pack(
            anchor="w", padx=8, pady=2
        )

        # dynamiczny opis – lista krytycznych usterek (ID)
        self.lbl_budynek_opis = ttk.Label(info, text="")
        self.lbl_budynek_opis.pack(
            anchor="w", padx=8, pady=2
        )

        # na starcie od razu przelicz stan i opis
        self._odswiez_opis_krytyczne()

        # ---- Monitoring systemów technicznych ----
        monitor = ttk.LabelFrame(top_row, text="Monitoring systemów technicznych")
        monitor.pack(side="left", fill="both", expand=True, padx=(5, 0))

        # Stan sieci
        self.lbl_net = ttk.Label(monitor, text="Stan sieci: -")
        self.lbl_net.grid(row=0, column=1, sticky="w", padx=8, pady=2)

        # Windy – tworzymy tyle etykiet, ile wind ma budynek (max 8)
        self.lbl_elevators = []
        if lw <= 0:
            self.lbl_elev1 = ttk.Label(monitor, text="Windy: (brak)")
            self.lbl_elev1.grid(row=0, column=0, sticky="w", padx=8, pady=2)
            self.lbl_elev2 = None
        else:
            max_windy = min(lw, len(self.elevators))
            for i in range(max_windy):
                lbl = ttk.Label(monitor, text=f"Winda {i + 1}: -")
                lbl.grid(row=0 + i, column=0, sticky="w", padx=8, pady=2)
                self.lbl_elevators.append(lbl)

            # dla kompatybilności zostawiamy też pierwsze dwie w osobnych atrybutach
            self.lbl_elev1 = self.lbl_elevators[0] if len(self.lbl_elevators) >= 1 else None
            self.lbl_elev2 = self.lbl_elevators[1] if len(self.lbl_elevators) >= 2 else None


        # Liczniki
        self.lbl_power = ttk.Label(monitor, text="Pobór prądu: -")
        self.lbl_power.grid(row=1, column=1, sticky="w", padx=8, pady=2)
        self.lbl_water = ttk.Label(monitor, text="Pobór wody: -")
        self.lbl_water.grid(row=2, column=1, sticky="w", padx=8, pady=2)

        # ---- Powiadomienia / zgłoszenia ----
        powiad = ttk.LabelFrame(frame, text="Powiadomienia / zgłoszenia dla tego budynku")
        powiad.pack(fill="both", expand=True, padx=10, pady=5)

        kol = ("ID", "Tytuł", "Status", "Utworzono")
        self.tabela_powiad = ttk.Treeview(
            powiad, columns=kol, show="headings", height=6
        )
        for k in kol:
            self.tabela_powiad.heading(k, text=k)
        self.tabela_powiad.column("ID", width=60)
        self.tabela_powiad.column("Tytuł", width=260)
        self.tabela_powiad.column("Status", width=120)
        self.tabela_powiad.column("Utworzono", width=160)
        self.tabela_powiad.pack(fill="both", expand=True, padx=8, pady=6)

        # ---- Wyjścia ewakuacyjne ----
        wyj_frame = ttk.LabelFrame(
            frame, text="Wyjścia ewakuacyjne / przeciwpożarowe"
        )
        wyj_frame.pack(fill="both", expand=True, padx=10, pady=5)

        kol_w = ("Piętro", "Wyjście", "Status")
        self.tabela_wyjsc = ttk.Treeview(
            wyj_frame, columns=kol_w, show="headings", height=6
        )
        for k in kol_w:
            self.tabela_wyjsc.heading(k, text=k)
        self.tabela_wyjsc.column("Piętro", width=60)
        self.tabela_wyjsc.column("Wyjście", width=80)
        self.tabela_wyjsc.column("Status", width=140)
        self.tabela_wyjsc.pack(fill="both", expand=True, padx=8, pady=4)

        self.lbl_wyjscia_podsum = ttk.Label(
            wyj_frame, text="Podsumowanie wyjść: -"
        )
        self.lbl_wyjscia_podsum.pack(anchor="w", padx=8, pady=2)


        # lista wyjść: generowana na podstawie parametrów budynku
        self.wyjscia = []
        try:
            lp = int(self.budynek.get("liczba_pieter", 0))
            wyj_na_p = int(self.budynek.get("wyjscia_na_pietro", 0))
        except (TypeError, ValueError):
            lp = 0
            wyj_na_p = 0
        # bezpiecznik – maksymalnie 20 wyjść na piętro
        if wyj_na_p > 0:
            wyj_na_p = min(wyj_na_p, 20)

        if lp > 0 and wyj_na_p > 0:
            # piętra numerujemy 0..lp-1 (lub 1..lp – wybierz jak wolisz)
            for pietro in range(lp+1):
                for nr in range(1, wyj_na_p + 1):
                    self.wyjscia.append((str(pietro), f"W{nr}"))

    # ---------- Motyw (jasny / ciemny) + zakładka Ustawienia ----------
    def _zastosuj_motyw(self):
        """
        Zastosuj aktualny motyw (jasny / ciemny) do głównego okna.
        Kolory są brane z ui.theme.get_colors().
        """
        apply_entry_style(self)
        colors = get_colors()

        # PRZELICZ styl Dark.TEntry po zmianie motywu

        # tło głównego okna
        self.configure(bg=colors["bg"])

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # --- ogólne tła / tekst ---
        style.configure(
            "TFrame",
            background=colors["bg"],
        )
        style.configure(
            "Card.TFrame",
            background=colors["card_bg"],
        )
        style.configure(
            "TLabelframe",
            background=colors["card_bg"],
            bordercolor=colors["border"],
        )
        style.configure(
            "TLabelframe.Label",
            background=colors["card_bg"],
            foreground=colors["text"],
        )
        style.configure(
            "TLabel",
            background=colors["bg"],
            foreground=colors["text"],
        )
        style.configure(
            "Header.TLabel",
            background=colors["bg"],
            foreground=colors["text"],
            font=("Segoe UI", 14, "bold"),
        )

        style.configure(
            "TButton",
            font=("Segoe UI", 9),
        )

        # --- Entry (pola tekstowe) ---
        style.configure(
            "TEntry",
            fieldbackground=colors["input_bg"],
            background=colors["input_bg"],
            foreground=colors["text"],
            bordercolor=colors["input_border"],
        )

        # dopilnuj też naszego własnego stylu
        style.configure(
            "Dark.TEntry",
            fieldbackground=colors["input_bg"],
            background=colors["input_bg"],
            foreground=colors["text"],
            bordercolor=colors["input_border"],
        )

        # --- Notebook (zakładki) ---
        style.configure(
            "TNotebook",
            background=colors["bg"],
            borderwidth=0,
            relief="flat",
            tabmargins=(6, 4, 6, 0),  # marginesy wokół całego paska zakładek
        )

        style.configure(
            "TNotebook.Tab",
            background=colors["card_bg"],
            foreground=colors["muted"],
            padding=(14, 6),     # większy „klik”, ładniejszy wygląd
            borderwidth=0,
            relief="flat",
        )

        style.configure(
            "Settings.TRadiobutton",
            background=colors["card_bg"],
            foreground=colors["text"],
        )
        style.map(
            "Settings.TRadiobutton",
            background=[("active", colors["card_bg"])],
            foreground=[("disabled", colors["muted"])],
        )

        style.map(
            "TNotebook.Tab",
            background=[
                ("selected", colors["bg"]),       # aktywna zakładka trochę jaśniejsza
                ("!selected", colors["card_bg"]),
            ],
            foreground=[
                ("selected", colors["text"]),
                ("!selected", colors["muted"]),
            ],

        )


        # --- Treeview (tabele) ---
        style.layout("DarkTreeview", style.layout("Treeview"))

        style.configure(
            "Treeview",
            background=colors["card_bg"],
            foreground=colors["text"],
            fieldbackground=colors["card_bg"],
            bordercolor=colors["border"],
            rowheight=20,
        )
        style.configure(
            "Treeview.Heading",
            background=colors["bg"],
            foreground=colors["text"],
            bordercolor=colors["border"],
        )

        # odśwież tła istniejących widgetów, które nie mają stylu
        # (np. root frame, jeśli jest tk.Frame)
        for child in self.winfo_children():
            if isinstance(child, tk.Frame):
                child.configure(bg=colors["bg"])

        # odśwież kolory widgetów tk.*, które nie używają ttk.Style
        self._odswiez_kolory_listboxow()

        # pole "Opis usterki" to tk.Text – też trzeba je ręcznie przemalować
        if hasattr(self, "opis_text"):
            self.opis_text.config(
                bg=colors["input_bg"],
                fg=colors["text"],
                insertbackground=colors["text"],
                highlightbackground=colors["input_border"],
            )


    def _odswiez_kolory_listboxow(self):
        """Aktualizuje kolory zwykłych tk.Listbox po zmianie motywu."""
        colors = get_colors()
        input_bg = colors["input_bg"]
        input_border = colors["input_border"]

        # listbox z przypisanymi budynkami (zakładka konta)
        if hasattr(self, "lista_budynkow_konta"):
            self.lista_budynkow_konta.config(
                bg=input_bg,
                fg=colors["text"],
                selectbackground=colors["accent"],
                selectforeground="white",
                highlightbackground=input_border,
            )

    def _on_zmiana_motywu(self):
        """Reakcja na zmianę trybu jasny/ciemny z zakładki Ustawienia."""
        self.tryb_ciemny = bool(self.tryb_ciemny_var.get())

        # zapamiętaj wybrany motyw w module theme.py
        if self.tryb_ciemny:
            set_theme("dark")
        else:
            set_theme("light")

        self._zastosuj_motyw()

    def _buduj_ustawienia(self, frame):
        """
        Zakładka 'Ustawienia' dostępna dla wszystkich użytkowników:
        - tryb jasny/ciemny
        - zmiana hasła
        - nowy losowy token do odzyskiwania hasła
        """
        # ---- MOTYW ----
        sek_motyw = ttk.LabelFrame(frame, text="Wygląd")
        sek_motyw.pack(fill="x", padx=10, pady=8)

        # Zawsze bierz aktualny motyw z theme.py (zapamiętany globalnie)
        aktualny_motyw = get_theme()
        self.tryb_ciemny = (aktualny_motyw == "dark")
        self.tryb_ciemny_var = tk.BooleanVar(value=self.tryb_ciemny)


        ttk.Label(sek_motyw, text="Tryb kolorystyczny:").grid(
            row=0, column=0, sticky="w", padx=6, pady=4
        )

        rb_jasny = ttk.Radiobutton(
            sek_motyw,
            text="Jasny",
            variable=self.tryb_ciemny_var,
            value=False,
            command=self._on_zmiana_motywu,
            style="Settings.TRadiobutton",
        )
        rb_jasny.grid(row=0, column=1, sticky="w", padx=6, pady=4)

        rb_ciemny = ttk.Radiobutton(
            sek_motyw,
            text="Ciemny",
            variable=self.tryb_ciemny_var,
            value=True,
            command=self._on_zmiana_motywu,
            style="Settings.TRadiobutton",
        )
        rb_ciemny.grid(row=0, column=2, sticky="w", padx=6, pady=4)

        for i in range(3):
            sek_motyw.columnconfigure(i, weight=1)

        # ---- ZMIANA HASŁA ----
        sek_haslo = ttk.LabelFrame(frame, text="Zmiana hasła")
        sek_haslo.pack(fill="x", padx=10, pady=8)

        ttk.Label(sek_haslo, text="Stare hasło:").grid(
            row=0, column=0, sticky="w", padx=6, pady=3
        )
        self.haslo_stare_entry = ttk.Entry(sek_haslo, width=25, show="*", style="Dark.TEntry")
        self.haslo_stare_entry.grid(row=0, column=1, sticky="w", padx=6, pady=3)

        ttk.Label(sek_haslo, text="Nowe hasło:").grid(
            row=1, column=0, sticky="w", padx=6, pady=3
        )
        self.haslo_nowe_entry = ttk.Entry(sek_haslo, width=25, show="*", style="Dark.TEntry")
        self.haslo_nowe_entry.grid(row=1, column=1, sticky="w", padx=6, pady=3)

        ttk.Label(sek_haslo, text="Powtórz nowe hasło:").grid(
            row=2, column=0, sticky="w", padx=6, pady=3
        )
        self.haslo_powtorz_entry = ttk.Entry(sek_haslo, width=25, show="*", style="Dark.TEntry")
        self.haslo_powtorz_entry.grid(row=2, column=1, sticky="w", padx=6, pady=3)

        btn_zmien_haslo = ttk.Button(
            sek_haslo,
            text="Zapisz nowe hasło",
            command=self._zmien_haslo_z_ustawien,
        )
        btn_zmien_haslo.grid(row=0, column=2, rowspan=3, sticky="nsw", padx=6, pady=3)

        for i in range(3):
            sek_haslo.columnconfigure(i, weight=1)

        # ---- TOKEN DO RESETU HASŁA ----
        sek_token = ttk.LabelFrame(frame, text="Token do zmiany/odzyskiwania hasła")
        sek_token.pack(fill="x", padx=10, pady=8)

        u = pobierz_uzytkownika_po_loginie(self.uzytkownik["login"])
        aktualny_token = u[4] if u else None

        ttk.Label(
            sek_token,
            text=(
                "Token służy do resetowania hasła w oknie 'Reset hasła'.\n"
                "Kliknij przycisk, aby wygenerować nowy losowy token."
            ),
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=4)

        ttk.Label(sek_token, text="Aktualny token:").grid(
            row=1, column=0, sticky="w", padx=6, pady=4
        )
        self.lbl_token_aktualny = ttk.Label(
            sek_token,
            text=aktualny_token or "(brak ustawionego tokenu)",
        )
        self.lbl_token_aktualny.grid(row=1, column=1, sticky="w", padx=6, pady=4)

        btn_nowy_token = ttk.Button(
            sek_token,
            text="Wygeneruj nowy token",
            command=self._generuj_nowy_token,
        )
        btn_nowy_token.grid(row=2, column=0, columnspan=2, sticky="w", padx=6, pady=6)

        for i in range(2):
            sek_token.columnconfigure(i, weight=1)

    def _zmien_haslo_z_ustawien(self):
        stare = self.haslo_stare_entry.get()
        nowe1 = self.haslo_nowe_entry.get()
        nowe2 = self.haslo_powtorz_entry.get()

        if not stare or not nowe1 or not nowe2:
            messagebox.showwarning("Błąd", "Uzupełnij wszystkie pola hasła.")
            return

        if nowe1 != nowe2:
            messagebox.showwarning("Błąd", "Nowe hasła nie są identyczne.")
            return

        u = pobierz_uzytkownika_po_loginie(self.uzytkownik["login"])
        if not u:
            messagebox.showerror("Błąd", "Nie znaleziono danych użytkownika.")
            return

        aktualne_haslo = u[2]
        if stare != aktualne_haslo:
            messagebox.showwarning("Błąd", "Stare hasło jest nieprawidłowe.")
            return

        if len(nowe1) < 4:
            messagebox.showwarning("Błąd", "Hasło powinno mieć co najmniej 4 znaki.")
            return

        if not ustaw_haslo(self.uzytkownik["login"], nowe1):
            messagebox.showerror("Błąd", "Nie udało się zaktualizować hasła.")
            return

        messagebox.showinfo("OK", "Hasło zostało zmienione.")
        self.haslo_stare_entry.delete(0, "end")
        self.haslo_nowe_entry.delete(0, "end")
        self.haslo_powtorz_entry.delete(0, "end")

    def _generuj_nowy_token(self):
        token = "".join(random.choices(string.ascii_uppercase + string.digits, k=12))
        try:
            ok = ustaw_token_reset(self.uzytkownik["login"], token)
        except Exception as e:
            messagebox.showerror(
                "Błąd", f"Nie udało się ustawić nowego tokenu:\n{e}"
            )
            return

        if not ok:
            messagebox.showerror("Błąd", "Nie udało się zaktualizować tokenu.")
            return

        self.lbl_token_aktualny.config(text=token)
        messagebox.showinfo(
            "Nowy token",
            f"Nowy token do resetu hasła został zapisany:\n{token}",
        )

    def _buduj_przeglady_techniczne(self, frame):
        """
        Zakładka widoczna dla PRACOWNIK – podgląd ostatnich przeglądów
        rocznych dla przypisanego budynku (po jednym wierszu na typ).
        """
        if not self.budynek:
            ttk.Label(
                frame,
                text="Brak przypisanego budynku do tego użytkownika – "
                     "nie można wyświetlić przeglądów.",
            ).pack(anchor="w", padx=10, pady=10)
            return

        naglowek = ttk.LabelFrame(
            frame,
            text=f"Przeglądy techniczne – {self.budynek['nazwa']}",
        )
        naglowek.pack(fill="both", expand=True, padx=10, pady=10)

        opis = (
            "Wykaz corocznych przeglądów: instalacja gazowa, kominiarska, "
            "instalacja elektryczna, windy, p.pożar, instalacja kanalizacyjna.\n"
            "Tabela poniżej pokazuje datę ostatniego przeglądu danego typu, "
            "koniec ważności oraz technika umawiającego wizytę."
        )
        ttk.Label(naglowek, text=opis, wraplength=820, justify="left").pack(
            anchor="w", padx=8, pady=(4, 8)
        )

        kolumny = (
            "Typ przeglądu",
            "Data ostatniego przeglądu",
            "Koniec ważności",
            "Technik",
        )
        self.tabela_przeglady = ttk.Treeview(
            naglowek,
            columns=kolumny,
            show="headings",
            height=14,
        )

        for k in kolumny:
            self.tabela_przeglady.heading(k, text=k)

        self.tabela_przeglady.column("Typ przeglądu", width=230, anchor="w")
        self.tabela_przeglady.column(
            "Data ostatniego przeglądu", width=150, anchor="center"
        )
        self.tabela_przeglady.column("Koniec ważności", width=130, anchor="center")
        self.tabela_przeglady.column("Technik", width=220, anchor="w")

        self.tabela_przeglady.pack(fill="both", expand=True, padx=8, pady=6)

        # dwuklik w wiersz – historia przeglądów danego typu
        self.tabela_przeglady.bind("<Double-1>", self._pokaz_historie_przegladu)

        # pierwsze załadowanie danych
        self.odswiez_przeglady()

    def _buduj_przeglady_techniczne_admin(self, frame):
        """
        Zakładka dla TECHNIK / ADMIN – ostatnie przeglądy + formularz
        dodawania nowego przeglądu.
        """
        if not self.budynek:
            ttk.Label(
                frame,
                text="Brak przypisanego budynku do tego użytkownika – "
                     "nie można wyświetlić ani dodać przeglądów.",
            ).pack(anchor="w", padx=10, pady=10)
            return

        # --- Pasek z informacją/wyborem budynku ---
        pasek_budynek = ttk.Frame(frame)
        pasek_budynek.pack(fill="x", padx=10, pady=(8, 0))

        ttk.Label(pasek_budynek, text="Budynek:").pack(side="left", padx=(0, 4))

        if self.uzytkownik.get("rola") == "ADMIN":
            # ADMIN – może przełączać budynki
            self.budynek_var = tk.StringVar()

            # budynki dostępne dla zalogowanego użytkownika (dla ADMINA – wszystkie)
            self.budynki_dostepne = lista_budynkow_dla_uzytkownika(
                self.uzytkownik["id"]
            )
            self.budynek_id_map = {}
            nazwy_budynkow = []

            for bid, nazwa in self.budynki_dostepne:
                nazwy_budynkow.append(nazwa)
                self.budynek_id_map[nazwa] = bid

            aktualna_nazwa = self.budynek.get("nazwa") if self.budynek else None

            if aktualna_nazwa and aktualna_nazwa in self.budynek_id_map:
                self.budynek_var.set(aktualna_nazwa)
            elif nazwy_budynkow:
                # jeśli current nie pasuje, ustaw pierwszy z listy
                self.budynek_var.set(nazwy_budynkow[0])
                if not aktualna_nazwa or aktualna_nazwa != nazwy_budynkow[0]:
                    # zsynchronizuj self.budynek
                    self._zmien_budynek_po_nazwie(nazwy_budynkow[0])

            self.budynek_combo = ttk.Combobox(
                pasek_budynek,
                textvariable=self.budynek_var,
                values=nazwy_budynkow,
                state="readonly",
                width=30,
            )
            self.budynek_combo.pack(side="left")
            self.budynek_combo.bind("<<ComboboxSelected>>", self._on_budynek_zmieniony)

        else:
            # TECHNIK – tylko informacja, bez zmiany budynku
            ttk.Label(
                pasek_budynek,
                text=self.budynek["nazwa"] if self.budynek else "(brak)",
            ).pack(side="left", padx=4)

            self.budynek_var = None
            self.budynek_id_map = {}

        # --- Główna ramka z przeglądami ---
        self.przeglady_naglowek = ttk.LabelFrame(
            frame,
            text=f"Przeglądy techniczne – {self.budynek['nazwa']}",
        )
        naglowek = self.przeglady_naglowek
        naglowek.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Formularz dodawania przeglądu ---
        form = ttk.Frame(naglowek)
        form.pack(fill="x", padx=8, pady=(6, 10))

        ttk.Label(form, text="Typ przeglądu:").grid(
            row=0, column=0, sticky="w", padx=4, pady=2
        )
        self.przegl_typ_var = tk.StringVar()
        wartosci_typow = [PRZEGLADY_NAZWY[t] for t in PRZEGLADY_TYPY]
        if wartosci_typow:
            self.przegl_typ_var.set(wartosci_typow[0])
        self.przegl_typ_combo = ttk.Combobox(
            form,
            textvariable=self.przegl_typ_var,
            values=wartosci_typow,
            state="readonly",
            width=28,
        )
        self.przegl_typ_combo.grid(row=0, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(form, text="Data wizyty (RRRR-MM-DD):").grid(
            row=0, column=2, sticky="w", padx=4, pady=2
        )
        self.przegl_data_entry = ttk.Entry(form, width=14, style="Dark.TEntry")
        self.przegl_data_entry.grid(row=0, column=3, sticky="w", padx=4, pady=2)
        self.przegl_data_entry.insert(
            0, datetime.date.today().strftime("%Y-%m-%d")
        )

        ttk.Label(form, text="Technik:").grid(
            row=1, column=0, sticky="w", padx=4, pady=2
        )

        # technik = zawsze login zalogowanego użytkownika, pole tylko do odczytu
        self.przegl_technik_var = tk.StringVar(value=self.uzytkownik["login"])
        self.przegl_technik_entry = ttk.Entry(
            form,
            width=25,
            textvariable=self.przegl_technik_var,
            state="readonly",
            style="Dark.TEntry",
        )
        self.przegl_technik_entry.grid(row=1, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(form, text="Uwagi:").grid(
            row=1, column=2, sticky="w", padx=4, pady=2
        )
        self.przegl_uwagi_entry = ttk.Entry(form, width=40, style="Dark.TEntry")
        self.przegl_uwagi_entry.grid(row=1, column=3, sticky="we", padx=4, pady=2)

        btn = ttk.Button(
            form,
            text="Dodaj przegląd",
            command=self._dodaj_przeglad_admin,
        )
        btn.grid(row=0, column=4, rowspan=2, sticky="nsw", padx=8, pady=2)

        form.columnconfigure(3, weight=1)

        # --- Tabela z ostatnimi przeglądami ---
        kolumny = (
            "Typ przeglądu",
            "Data ostatniego przeglądu",
            "Koniec ważności",
            "Technik",
        )
        self.tabela_przeglady = ttk.Treeview(
            naglowek,
            columns=kolumny,
            show="headings",
            height=12,
        )

        for k in kolumny:
            self.tabela_przeglady.heading(k, text=k)

        self.tabela_przeglady.column("Typ przeglądu", width=230, anchor="w")
        self.tabela_przeglady.column(
            "Data ostatniego przeglądu", width=150, anchor="center"
        )
        self.tabela_przeglady.column("Koniec ważności", width=130, anchor="center")
        self.tabela_przeglady.column("Technik", width=220, anchor="w")

        self.tabela_przeglady.pack(fill="both", expand=True, padx=8, pady=6)

        # dwuklik – historia
        self.tabela_przeglady.bind("<Double-1>", self._pokaz_historie_przegladu)

        # pierwsze załadowanie danych dla aktualnego budynku
        self.odswiez_przeglady()

    def _dodaj_przeglad_admin(self):
        """
        Dodaje nowy przegląd techniczny (TECHNIK / ADMIN).
        """
        if not self.budynek:
            messagebox.showerror("Błąd", "Brak przypisanego budynku.")
            return

        nazwa_typu = self.przegl_typ_var.get().strip()
        if not nazwa_typu:
            messagebox.showwarning("Błąd", "Wybierz typ przeglądu.")
            return
        typ = PRZEGLADY_NAZWY_ODWROTNIE.get(nazwa_typu, nazwa_typu)

        data_wizyty = self.przegl_data_entry.get().strip()
        # technik = zawsze login aktualnie zalogowanego użytkownika
        technik = self.uzytkownik["login"]
        uwagi = self.przegl_uwagi_entry.get().strip() or None

        if not data_wizyty:
            messagebox.showwarning("Błąd", "Podaj datę wizyty.")
            return

        try:
            # prosta walidacja formatu – jeśli się nie uda, poleci wyjątek
            datetime.date.fromisoformat(data_wizyty)
        except ValueError:
            messagebox.showwarning(
                "Błąd",
                "Niepoprawny format daty. Użyj RRRR-MM-DD, np. 2025-01-15.",
            )
            return

        try:
            dodaj_przeglad_techniczny(
                self.budynek["id"], typ, data_wizyty, technik, uwagi
            )
        except Exception as e:
            messagebox.showerror(
                "Błąd",
                f"Nie udało się dodać przeglądu:\n{e}",
            )
            return

        messagebox.showinfo("Sukces", "Przegląd został zapisany.")
        self.odswiez_przeglady()


    # ---------- Aktualizacja pulpitu ----------
    def odswiez_pulpit(self):
        if self.uzytkownik["rola"] not in ("PRACOWNIK", "TECHNIK"):
            return
        if not self.budynek or not self.tabela_powiad:
            return

        # zgłoszenia dla budynku
        for item in self.tabela_powiad.get_children():
            self.tabela_powiad.delete(item)
        for r in lista_zgloszen_dla_budynku(self.budynek["id"]):
            self.tabela_powiad.insert("", "end", values=(r[0], r[1], r[2], r[3]))

        # odśwież opis dotyczący krytycznych usterek
        self._odswiez_opis_krytyczne()

    def _odswiez_opis_krytyczne(self):
        """Aktualizuje opis krytycznych usterek i stan budynku na pulpicie."""
        # dotyczy pulpitów PRACOWNIK / TECHNIK
        if self.uzytkownik["rola"] not in ("PRACOWNIK", "TECHNIK"):
            return
        if not self.budynek:
            return

        rows = lista_krytycznych_dla_budynku(self.budynek["id"])

        if rows:
            # są krytyczne usterki
            ids = ", ".join(str(r[0]) for r in rows)
            opis = f"Krytyczne usterki – ID: {ids}"
            stan = "Krytyczny"
        else:
            # brak krytycznych usterek
            opis = "Brak aktywnych krytycznych usterek."
            stan = "Stabilny"

        if self.lbl_budynek_opis is not None:
            self.lbl_budynek_opis.config(text=opis)

        if self.lbl_budynek_stan is not None:
            self.lbl_budynek_stan.config(text=f"Stan: {stan}")

    def odswiez_przeglady(self):
        """Odświeża tabelę z przeglądami technicznymi (jeśli istnieje)."""
        if not hasattr(self, "tabela_przeglady") or self.tabela_przeglady is None:
            return
        if not self.budynek:
            return

        for item in self.tabela_przeglady.get_children():
            self.tabela_przeglady.delete(item)

        try:
            wiersze = ostatnie_przeglady_dla_budynku(self.budynek["id"])
        except Exception as e:
            messagebox.showerror(
                "Błąd",
                f"Nie udało się pobrać listy przeglądów technicznych:\n{e}",
            )
            return

        for typ, data_ost, data_koniec, technik in wiersze:
            nazwa_typu = PRZEGLADY_NAZWY.get(typ, typ)
            self.tabela_przeglady.insert(
                "",
                "end",
                values=(
                    nazwa_typu,
                    data_ost or "-",
                    data_koniec or "-",
                    technik or "-",
                ),
            )


        def _pokaz_historie_przegladu(self, _evt=None):
            """
            Dwuklik w wiersz tabeli przeglądów – otwiera okno z historią
            przeglądów danego typu.
            """
            if not self.budynek or not self.tabela_przeglady:
                return

            sel = self.tabela_przeglady.focus()
            if not sel:
                return
            wartosci = self.tabela_przeglady.item(sel)["values"]
            if not wartosci:
                return

            nazwa_typu = wartosci[0]
            typ = PRZEGLADY_NAZWY_ODWROTNIE.get(nazwa_typu, nazwa_typu)

            try:
                wiersze = historia_przegladow_dla_budynku_i_typu(
                    self.budynek["id"], typ
                )
            except Exception as e:
                messagebox.showerror(
                    "Błąd",
                    f"Nie udało się pobrać historii przeglądów:\n{e}",
                )
                return

            okno = tk.Toplevel(self)
            okno.title(f"Historia przeglądów – {nazwa_typu}")
            okno.geometry("600x400")

            kolumny = ("Data wizyty", "Technik", "Uwagi")
            tree = ttk.Treeview(okno, columns=kolumny, show="headings")
            for k in kolumny:
                tree.heading(k, text=k)

            tree.column("Data wizyty", width=110, anchor="center")
            tree.column("Technik", width=160, anchor="w")
            tree.column("Uwagi", width=280, anchor="w")
            tree.pack(fill="both", expand=True, padx=8, pady=8)

            for data_wizyty, technik, uwagi in wiersze:
                tree.insert("", "end", values=(data_wizyty, technik, uwagi or ""))

            if not wiersze:
                ttk.Label(
                    okno,
                    text="Brak zarejestrowanych przeglądów tego typu.",
                ).pack(anchor="w", padx=8, pady=4)

    def _on_budynek_zmieniony(self, _evt=None):
        """Handler zmiany budynku w comboboxie (przeglądy TECHNIK/ADMIN)."""
        if not self.budynek_var:
            return
        nazwa = self.budynek_var.get()
        self._zmien_budynek_po_nazwie(nazwa)

    def _zmien_budynek_po_nazwie(self, nazwa):
        """Ustawia self.budynek na podstawie nazwy i odświeża widoki."""
        if not nazwa:
            return
        bid = self.budynek_id_map.get(nazwa)
        if not bid:
            return

        try:
            nowy_budynek = pobierz_budynek_po_id(bid)
        except Exception as e:
            messagebox.showerror(
                "Błąd",
                f"Nie udało się przełączyć budynku:\n{e}",
                parent=self,
            )
            return

        if not nowy_budynek:
            return

        # podmieniamy aktualny budynek
        self.budynek = nowy_budynek

        # aktualizacja nagłówka ramki z przeglądami
        if self.przeglady_naglowek is not None:
            self.przeglady_naglowek.config(
                text=f"Przeglądy techniczne – {self.budynek['nazwa']}"
            )

        # odśwież tabelę z ostatnimi przeglądami
        self.odswiez_przeglady()


    # ---------- Karty: konta użytkowników (ADMIN) ----------

    def _buduj_konta_uzytkownikow(self, frame):
        """
        Zakładka widoczna tylko dla ADMIN:
        - lista wszystkich kont
        - szczegóły zaznaczonego konta
        - możliwość przypisania WIELU budynków (pracownik/technik)
        - Admin ma automatycznie wszystkie budynki i nie można mu ich edytować
        """

        # --- FILTRY KONT ---
        filtry = ttk.LabelFrame(
            frame,
            text="Filtry kont (ID / login / rola / budynek)",
        )
        filtry.pack(fill="x", padx=8, pady=(8, 4))

        # --- przyciski akcji admina (użytkownicy / budynki) ---
        panel_akcji = ttk.Frame(frame)
        panel_akcji.pack(fill="x", padx=8, pady=(0, 4))

        self.btn_dodaj_uzytkownika = ttk.Button(
            panel_akcji,
            text="Dodaj użytkownika",
            command=self._pokaz_okno_dodaj_uzytkownika,
        )
        self.btn_dodaj_uzytkownika.grid(row=0, column=0, sticky="w", padx=4, pady=2)

        self.btn_edytuj_uzytkownika = ttk.Button(
            panel_akcji,
            text="Edytuj użytkownika",
            command=self._otworz_okno_edycji_konta,
            state="disabled",   # włączymy po zaznaczeniu wiersza
        )
        self.btn_edytuj_uzytkownika.grid(row=0, column=1, sticky="w", padx=4, pady=2)

        # NOWY PRZYCISK – USUŃ UŻYTKOWNIKA
        self.btn_usun_uzytkownika = ttk.Button(
            panel_akcji,
            text="Usuń użytkownika",
            command=self._usun_konto_z_listy,
            state="disabled",   # aktywny dopiero po zaznaczeniu konta
        )
        self.btn_usun_uzytkownika.grid(row=0, column=2, sticky="w", padx=4, pady=2)

        self.btn_dodaj_budynek = ttk.Button(
            panel_akcji,
            text="Dodaj budynek",
            command=self._pokaz_okno_dodaj_budynek,
        )
        self.btn_dodaj_budynek.grid(row=0, column=3, sticky="w", padx=4, pady=2)

        self.btn_usun_budynek = ttk.Button(
            panel_akcji,
            text="Usuń budynek",
            command=self._pokaz_okno_usun_budynek,
        )
        self.btn_usun_budynek.grid(row=0, column=4, sticky="w", padx=4, pady=2)

        self.btn_edytuj_budynek = ttk.Button(
            panel_akcji,
            text="Edytuj budynek",
            command=self._pokaz_okno_edytuj_budynek,
        )
        self.btn_edytuj_budynek.grid(row=0, column=5, sticky="w", padx=4, pady=2)

        panel_akcji.columnconfigure(6, weight=1)

        panel_akcji.columnconfigure(5, weight=1)

        self.filter_konto_id_var = tk.StringVar()
        self.filter_konto_login_var = tk.StringVar()
        self.filter_konto_rola_var = tk.StringVar(value="(wszystkie)")
        self.filter_konto_budynek_var = tk.StringVar()

        ttk.Label(filtry, text="ID zawiera:").grid(
            row=0, column=0, sticky="w", padx=4, pady=2
        )
        e_id = ttk.Entry(
            filtry,
            width=10,
            textvariable=self.filter_konto_id_var,
            style="Dark.TEntry",
        )
        e_id.grid(row=0, column=1, sticky="w", padx=4, pady=2)
        e_id.bind("<KeyRelease>", lambda _e: self._zastosuj_filtry_konta())

        ttk.Label(filtry, text="Login zawiera:").grid(
            row=0, column=2, sticky="w", padx=4, pady=2
        )
        e_login = ttk.Entry(filtry, width=18, textvariable=self.filter_konto_login_var, style="Dark.TEntry")
        e_login.grid(row=0, column=3, sticky="w", padx=4, pady=2)
        e_login.bind("<KeyRelease>", lambda _e: self._zastosuj_filtry_konta())

        ttk.Label(filtry, text="Rola:").grid(
            row=1, column=0, sticky="w", padx=4, pady=2
        )
        self.filter_konto_rola_combo = ttk.Combobox(
            filtry,
            width=12,
            state="readonly",
            textvariable=self.filter_konto_rola_var,
            values=["(wszystkie)", "PRACOWNIK", "TECHNIK", "ADMIN"],
        )
        self.filter_konto_rola_combo.grid(row=1, column=1, sticky="w", padx=4, pady=2)
        self.filter_konto_rola_combo.bind(
            "<<ComboboxSelected>>", lambda _e: self._zastosuj_filtry_konta()
        )

        ttk.Label(filtry, text="Budynek zawiera:").grid(
            row=1, column=2, sticky="w", padx=4, pady=2
        )
        e_bud = ttk.Entry(
            filtry, width=18, textvariable=self.filter_konto_budynek_var, style="Dark.TEntry"
        )
        e_bud.grid(row=1, column=3, sticky="w", padx=4, pady=2)
        e_bud.bind("<KeyRelease>", lambda _e: self._zastosuj_filtry_konta())

        btn_wycz = ttk.Button(
            filtry, text="Wyczyść filtry", command=self._wyczysc_filtry_konta
        )
        btn_wycz.grid(row=0, column=4, rowspan=2, sticky="e", padx=4, pady=2)

        filtry.columnconfigure(3, weight=1)

        # --- tabela kont ---
        kolumny = (
            "ID",
            "Login",
            "Rola",
            "Budynki",
            "Ostatnie logowanie",
            "Hasło (podgląd)",
        )
        self.tabela_konta = ttk.Treeview(
            frame, columns=kolumny, show="headings", height=14
        )

        # stan sortowania kont
        self._sort_konta_column = None  # nazwa kolumny
        self._sort_konta_order = None  # "asc" / "desc" / None
        self._wszystkie_konta = []  # pełna lista rekordów (do filtrowania i sortu)

        for k in kolumny:
            if k == "Hasło (podgląd)":
                # po tej kolumnie NIE sortujemy
                self.tabela_konta.heading(k, text=k)
            else:
                self.tabela_konta.heading(
                    k,
                    text=k,
                    command=lambda c=k: self._klik_naglowek_konta(c),
                )

        self.tabela_konta.column("ID", width=60, anchor="center")
        self.tabela_konta.column("Login", width=140, anchor="w")
        self.tabela_konta.column("Rola", width=100, anchor="center")
        self.tabela_konta.column("Budynki", width=220, anchor="w")
        self.tabela_konta.column("Ostatnie logowanie", width=160, anchor="center")
        self.tabela_konta.column("Hasło (podgląd)", width=140, anchor="center")

        self.tabela_konta.pack(fill="both", expand=True, padx=8, pady=8)

        self.tabela_konta.bind("<<TreeviewSelect>>", self._on_select_konto)

        # podwójny klik w wiersz -> okno zmiany loginu/hasła
        self.tabela_konta.bind("<Double-1>", self._otworz_okno_edycji_konta)


        # mapa: item_id -> dane konta
        self.konta_map = {}

        # ---- panel szczegółów ----
        det = ttk.LabelFrame(frame, text="Szczegóły zaznaczonego konta")
        det.pack(fill="both", padx=8, pady=(0, 8))

        self.lbl_konto_login = ttk.Label(det, text="Login: -")
        self.lbl_konto_login.grid(row=0, column=0, sticky="w", padx=6, pady=2)

        self.lbl_konto_rola = ttk.Label(det, text="Rola: -")
        self.lbl_konto_rola.grid(row=1, column=0, sticky="w", padx=6, pady=2)

        self.lbl_konto_haslo = ttk.Label(det, text="Hasło: -")
        self.lbl_konto_haslo.grid(row=2, column=0, sticky="w", padx=6, pady=2)

        self.lbl_konto_logowanie = ttk.Label(det, text="Ostatnie logowanie: -")
        self.lbl_konto_logowanie.grid(row=3, column=0, sticky="w", padx=6, pady=2)

        ttk.Label(det, text="Przypisane budynki:").grid(
            row=0, column=1, sticky="nw", padx=6, pady=2
        )
        colors = get_colors()
        input_bg = colors["input_bg"]
        input_border = colors["input_border"]
        self._buduj_konta_uzytkownikow
        # LISTBOX z wielokrotnym wyborem budynków
        self.lista_budynkow_konta = tk.Listbox(
            det,
            selectmode="extended",
            height=6,
            exportselection=False,
            bg=input_bg,
            fg=colors["text"],
            selectbackground=colors["accent"],
            selectforeground="white",
            relief="flat",
            highlightthickness=1,
            highlightbackground=input_border,
        )
        self.lista_budynkow_konta.grid(
            row=0, column=2, rowspan=3, sticky="nsew", padx=6, pady=2
        )

        self.btn_konto_zapisz = ttk.Button(
            det,
            text="Zapisz przypisane budynki",
            command=self._zapisz_budynek_konta,
        )
        self.btn_konto_zapisz.grid(row=3, column=2, sticky="e", padx=6, pady=4)

        # nowy przycisk – całkowite odebranie budynków
        self.btn_konto_usun_budynki = ttk.Button(
            det,
            text="Usuń przypisanie budynku",
            command=self._usun_budynki_konta,
        )
        self.btn_konto_usun_budynki.grid(row=3, column=1, sticky="w", padx=6, pady=4)


        det.columnconfigure(2, weight=1)
        det.rowconfigure(0, weight=1)

        # ładujemy listę budynków do listboxa
        self._zaladuj_budynki_do_kont()

        # wczytanie listy kont
        self.odswiez_konta()

    def _usun_konto_z_listy(self):
        """
        Usuwa wybranego użytkownika bezpośrednio z zakładki 'Zarządzanie'.
        Nie pozwala usuwać konta ADMIN.
        """
        if not hasattr(self, "aktualne_konto_id"):
            messagebox.showwarning("Brak wyboru", "Najpierw wybierz konto z listy.")
            return

        # znajdź info o wybranym koncie
        info = None
        for d in self.konta_map.values():
            if d["id"] == self.aktualne_konto_id:
                info = d
                break

        if info is None:
            messagebox.showerror("Błąd", "Nie znaleziono danych konta.")
            return

        if info["rola"] == "ADMIN":
            messagebox.showwarning(
                "Brak uprawnień",
                "Nie można usuwać kont typu ADMIN.",
            )
            return

        if not messagebox.askyesno(
            "Potwierdź",
            f"Czy na pewno chcesz usunąć użytkownika '{info['login']}'?",
        ):
            return

        try:
            usun_uzytkownika(info["id"])
        except Exception as e:
            messagebox.showerror(
                "Błąd",
                f"Nie udało się usunąć użytkownika:\n{e}",
            )
            return

        messagebox.showinfo("OK", "Użytkownik został usunięty.")
        self.odswiez_konta()

        # po usunięciu – dezaktywujemy przyciski edycji/usuwania
        if hasattr(self, "btn_edytuj_uzytkownika"):
            self.btn_edytuj_uzytkownika.config(state="disabled")
        if hasattr(self, "btn_usun_uzytkownika"):
            self.btn_usun_uzytkownika.config(state="disabled")


    def _pokaz_okno_dodaj_uzytkownika(self):
        """Okno dodawania nowego użytkownika (PRACOWNIK / TECHNIK)."""
        okno = tk.Toplevel(self)
        okno.title("Dodaj użytkownika")
        okno.resizable(False, False)
        okno.transient(self)
        okno.grab_set()
        try:
            okno.configure(bg=self["bg"])
        except Exception:
            pass

        frm = ttk.Frame(okno, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Login:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        entry_login = ttk.Entry(frm, width=26, style="Dark.TEntry")
        entry_login.grid(row=0, column=1, sticky="we", padx=4, pady=4)

        ttk.Label(frm, text="Hasło:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        entry_haslo = ttk.Entry(frm, width=26, show="*", style="Dark.TEntry")
        entry_haslo.grid(row=1, column=1, sticky="we", padx=4, pady=4)

        ttk.Label(frm, text="Typ konta:").grid(
            row=2, column=0, sticky="w", padx=4, pady=4
        )
        rola_var = tk.StringVar(value="PRACOWNIK")
        combo_rola = ttk.Combobox(
            frm,
            textvariable=rola_var,
            state="readonly",
            values=("PRACOWNIK", "TECHNIK"),
            width=22,
        )
        combo_rola.grid(row=2, column=1, sticky="w", padx=4, pady=4)

        def anuluj():
            okno.destroy()

        def potwierdz():
            login = (entry_login.get() or "").strip()
            haslo = (entry_haslo.get() or "").strip()
            rola = (rola_var.get() or "").strip()

            if not login or not haslo:
                messagebox.showwarning(
                    "Brak danych",
                    "Login i hasło są wymagane.",
                    parent=okno,
                )
                return

            if rola not in ("PRACOWNIK", "TECHNIK"):
                messagebox.showwarning(
                    "Błędna rola",
                    "Wybierz typ konta: PRACOWNIK lub TECHNIK.",
                    parent=okno,
                )
                return

            try:
                dodaj_uzytkownika(login, haslo, rola)
            except Exception as e:
                messagebox.showerror(
                    "Błąd",
                    f"Nie udało się dodać użytkownika:\n{e}",
                    parent=okno,
                )
                return

            messagebox.showinfo("OK", "Użytkownik został dodany.", parent=okno)
            okno.destroy()
            self.odswiez_konta()

        btns = ttk.Frame(frm)
        btns.grid(row=3, column=0, columnspan=2, sticky="e", pady=(10, 0))

        btn_ok = ttk.Button(btns, text="Potwierdź", command=potwierdz)
        btn_ok.pack(side="right", padx=4)

        btn_cancel = ttk.Button(btns, text="Anuluj", command=anuluj)
        btn_cancel.pack(side="right", padx=4)

        frm.columnconfigure(1, weight=1)
        entry_login.focus_set()
        self._wycentruj_okno(okno)

    def _pokaz_okno_usun_budynek(self):
        """Okno z listą budynków do usunięcia."""
        if self.okno_usun_budynek is not None and self.okno_usun_budynek.winfo_exists():
            self.okno_usun_budynek.lift()
            self.okno_usun_budynek.focus_force()
            return

        okno = tk.Toplevel(self)
        self.okno_usun_budynek = okno
        okno.bind("<Destroy>", lambda e: setattr(self, "okno_usun_budynek", None))

        okno.title("Usuń budynek")
        okno.resizable(False, False)
        okno.transient(self)
        okno.grab_set()
        okno.resizable(False, False)
        okno.transient(self)
        okno.grab_set()
        try:
            okno.configure(bg=self["bg"])
        except Exception:
            pass

        frm = ttk.Frame(okno, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(
            frm,
            text="Wybierz budynek do usunięcia:",
        ).grid(row=0, column=0, sticky="w", padx=4, pady=(0, 6))

        colors = get_colors()
        input_bg = colors["input_bg"]
        input_border = colors["input_border"]

        lista = tk.Listbox(
            frm,
            height=10,
            exportselection=False,
            bg=input_bg,
            fg=colors["text"],
            selectbackground=colors["accent"],
            selectforeground="white",
            relief="flat",
            highlightthickness=1,
            highlightbackground=input_border,
        )
        lista.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)


        scrollbar = ttk.Scrollbar(frm, orient="vertical", command=lista.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=4)
        lista.configure(yscrollcommand=scrollbar.set)

        # wczytaj budynki
        budynki = lista_budynkow()  # [(id, nazwa), ...]
        for bid, nazwa in budynki:
            lista.insert("end", f"{bid} – {nazwa}")

        def anuluj():
            okno.destroy()

        def usun_wybrany():
            sel = lista.curselection()
            if not sel:
                messagebox.showwarning(
                    "Brak wyboru",
                    "Najpierw wybierz budynek z listy.",
                    parent=okno,
                )
                return
            idx = sel[0]
            budynek_id = budynki[idx][0]
            nazwa = budynki[idx][1]

            if not messagebox.askyesno(
                "Potwierdź",
                f"Czy na pewno chcesz usunąć budynek '{nazwa}' (ID: {budynek_id})?",
                parent=okno,
            ):
                return

            try:
                usun_budynek(budynek_id)
            except Exception as e:
                messagebox.showerror(
                    "Błąd",
                    f"Nie udało się usunąć budynku:\n{e}",
                    parent=okno,
                )
                return

            messagebox.showinfo(
                "OK",
                "Budynek został usunięty.",
                parent=okno,
            )
            okno.destroy()
            self._zaladuj_budynki_do_kont()
            self.odswiez_konta()
            self._odswiez_budynki_admin()

        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, columnspan=2, sticky="e", pady=(10, 0))

        btn_usun = ttk.Button(btns, text="Usuń", command=usun_wybrany)
        btn_usun.pack(side="right", padx=4)

        btn_cancel = ttk.Button(btns, text="Anuluj", command=anuluj)
        btn_cancel.pack(side="right", padx=4)

        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(1, weight=1)
        self._wycentruj_okno(okno)

    def _pokaz_okno_edytuj_budynek(self):
        """Okno edycji danych budynku (ADMIN)."""
        if self.okno_edytuj_budynek is not None and self.okno_edytuj_budynek.winfo_exists():
            self.okno_edytuj_budynek.lift()
            self.okno_edytuj_budynek.focus_force()
            return

        okno = tk.Toplevel(self)
        self.okno_edytuj_budynek = okno
        okno.bind("<Destroy>", lambda e: setattr(self, "okno_edytuj_budynek", None))

        okno.title("Edytuj budynek")
        okno.resizable(False, False)
        okno.transient(self)
        okno.grab_set()
        okno.resizable(False, False)
        okno.transient(self)
        okno.grab_set()
        try:
            okno.configure(bg=self["bg"])
        except Exception:
            pass

        frm = ttk.Frame(okno, padding=10)
        frm.pack(fill="both", expand=True)

        # --- lewa strona: lista budynków ---
        lewa = ttk.Frame(frm)
        lewa.grid(row=0, column=0, sticky="nsw", padx=(0, 8))

        ttk.Label(lewa, text="Wybierz budynek:").pack(anchor="w")

        colors = get_colors()
        input_bg = colors["input_bg"]
        input_border = colors["input_border"]

        lista = tk.Listbox(
            lewa,
            height=10,
            exportselection=False,
            bg=input_bg,
            fg=colors["text"],
            selectbackground=colors["accent"],
            selectforeground="white",
            relief="flat",
            highlightthickness=1,
            highlightbackground=input_border,
        )
        lista.pack(side="left", fill="y", pady=(4, 0))


        scrollbar = ttk.Scrollbar(lewa, orient="vertical", command=lista.yview)
        scrollbar.pack(side="left", fill="y", pady=(4, 0))
        lista.configure(yscrollcommand=scrollbar.set)

        budynki = lista_budynkow()  # [(id, nazwa), ...]
        for bid, nazwa in budynki:
            lista.insert("end", f"{bid} – {nazwa}")

        # --- prawa strona: formularz danych ---
        prawa = ttk.LabelFrame(frm, text="Dane budynku")
        prawa.grid(row=0, column=1, sticky="nsew")

        ttk.Label(prawa, text="Nazwa budynku:").grid(
            row=0, column=0, sticky="w", padx=4, pady=4
        )
        nazwa_entry = ttk.Entry(prawa, width=30, style="Dark.TEntry")
        nazwa_entry.grid(row=0, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(prawa, text="Ulica (opcjonalnie):").grid(
            row=1, column=0, sticky="w", padx=4, pady=4
        )
        ulica_entry = ttk.Entry(prawa, width=30, style="Dark.TEntry")
        ulica_entry.grid(row=1, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(prawa, text="Kod pocztowy (opcjonalnie):").grid(
            row=2, column=0, sticky="w", padx=4, pady=4
        )
        kod_entry = ttk.Entry(prawa, width=15, style="Dark.TEntry")
        kod_entry.grid(row=2, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(prawa, text="Liczba pięter:").grid(
            row=3, column=0, sticky="w", padx=4, pady=4
        )
        pieter_entry = ttk.Entry(prawa, width=10, style="Dark.TEntry")
        pieter_entry.grid(row=3, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(prawa, text="Liczba wind:").grid(
            row=4, column=0, sticky="w", padx=4, pady=4
        )
        windy_entry = ttk.Entry(prawa, width=10, style="Dark.TEntry")
        windy_entry.grid(row=4, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(prawa, text="Wyjścia ewakuacyjne/p.poż na piętro:").grid(
            row=5, column=0, sticky="w", padx=4, pady=4
        )
        wyjscia_entry = ttk.Entry(prawa, width=10, style="Dark.TEntry")
        wyjscia_entry.grid(row=5, column=1, sticky="w", padx=4, pady=4)

        # --- funkcje pomocnicze ---

        def Zaladuj_z_listy(_evt=None):
            sel = lista.curselection()
            if not sel:
                return
            idx = sel[0]
            bud_id = budynki[idx][0]
            dane = pobierz_budynek_po_id(bud_id)
            if not dane:
                return

            nazwa_entry.delete(0, "end")
            nazwa_entry.insert(0, dane["nazwa"] or "")

            ulica_entry.delete(0, "end")
            ulica_entry.insert(0, dane["ulica"] or "")

            kod_entry.delete(0, "end")
            kod_entry.insert(0, dane["kod_pocztowy"] or "")

            pieter_entry.delete(0, "end")
            pieter_entry.insert(0, str(dane["liczba_pieter"]))

            windy_entry.delete(0, "end")
            windy_entry.insert(0, str(dane["liczba_wind"]))

            wyjscia_entry.delete(0, "end")
            wyjscia_entry.insert(0, str(dane["wyjscia_na_pietro"]))

        lista.bind("<<ListboxSelect>>", Zaladuj_z_listy)

        # automatycznie zaznacz pierwszy budynek
        if budynki:
            lista.selection_set(0)
            Zaladuj_z_listy()

        # --- przyciski na dole okna ---
        btns = ttk.Frame(frm)
        btns.grid(row=1, column=0, columnspan=2, sticky="e", pady=(10, 0))

        def anuluj():
            okno.destroy()

        def zapisz():
            sel = lista.curselection()
            if not sel:
                messagebox.showwarning(
                    "Brak wyboru",
                    "Najpierw wybierz budynek z listy.",
                    parent=okno,
                )
                return

            idx = sel[0]
            bud_id = budynki[idx][0]

            nazwa = (nazwa_entry.get() or "").strip()
            ulica = (ulica_entry.get() or "").strip()
            kod = (kod_entry.get() or "").strip()
            lp_txt = (pieter_entry.get() or "").strip()
            lw_txt = (windy_entry.get() or "").strip()
            wyj_txt = (wyjscia_entry.get() or "").strip()

            if not nazwa:
                messagebox.showwarning(
                    "Brak nazwy",
                    "Nazwa budynku jest wymagana.",
                    parent=okno,
                )
                return

            try:
                lp = int(lp_txt) if lp_txt else 10
                lw = int(lw_txt) if lw_txt else 2
                wyj = int(wyj_txt) if wyj_txt else 2
            except ValueError:
                messagebox.showwarning(
                    "Błąd danych",
                    "Liczba pięter, wind i wyjść na piętro musi być liczbą całkowitą.",
                    parent=okno,
                )
                return

            if lp <= 0 or lw <= 0 or wyj <= 0:
                messagebox.showwarning(
                    "Błędne wartości",
                    "Wszystkie wartości muszą być dodatnie.",
                    parent=okno,
                )
                return

            try:
                edytuj_budynek(
                    bud_id,
                    nazwa,
                    ulica,
                    kod,
                    stan="",
                    opis="",
                    liczba_pieter=lp,
                    liczba_wind=lw,
                    wyjscia_na_pietro=wyj,
                )
            except Exception as e:
                messagebox.showerror(
                    "Błąd",
                    f"Nie udało się zapisać zmian:\n{e}",
                    parent=okno,
                )
                return

            messagebox.showinfo(
                "OK",
                "Dane budynku zostały zaktualizowane.",
                parent=okno,
            )
            okno.destroy()
            # odśwież listę budynków / kont w zakładce admina
            self._zaladuj_budynki_do_kont()
            self.odswiez_konta()
            self._odswiez_budynki_admin()

        btn_zapisz = ttk.Button(btns, text="Zapisz zmiany", command=zapisz)
        btn_zapisz.pack(side="right", padx=4)

        btn_anuluj = ttk.Button(btns, text="Anuluj", command=anuluj)
        btn_anuluj.pack(side="right", padx=4)

        frm.columnconfigure(1, weight=1)
        self._wycentruj_okno(okno)


    def _zaladuj_budynki_do_kont(self):
        """Pomocnicze: wczytuje listę budynków do listboxa w zakładce kont."""
        self.budynki_lista = lista_budynkow()  # [(id, nazwa), ...]
        self.lista_budynkow_konta.delete(0, "end")
        for _bid, nazwa in self.budynki_lista:
            self.lista_budynkow_konta.insert("end", nazwa)

    def _odswiez_budynki_admin(self):
        """
        Odświeża combobox z budynkami w zakładce przeglądów (dla ADMINA).
        Wywoływana po dodaniu/edycji/usunięciu budynku.
        """
        # tylko ADMIN ma combobox do zmiany budynku
        if self.uzytkownik.get("rola") != "ADMIN":
            return

        # combobox istnieje dopiero po zbudowaniu zakładki przeglądów
        if not hasattr(self, "budynek_combo") or self.budynek_combo is None:
            return

        # pobierz aktualną listę budynków dla ADMINA (czyli wszystkie)
        self.budynki_dostepne = lista_budynkow_dla_uzytkownika(
            self.uzytkownik["id"]
        )
        self.budynek_id_map = {}
        nazwy_budynkow = []

        for bid, nazwa in self.budynki_dostepne:
            nazwy_budynkow.append(nazwa)
            self.budynek_id_map[nazwa] = bid

        # zaktualizuj wartości w comboboxie
        self.budynek_combo["values"] = nazwy_budynkow

        # spróbuj zostawić obecnie wybrany budynek
        aktualna_nazwa = self.budynek.get("nazwa") if self.budynek else None
        if aktualna_nazwa and aktualna_nazwa in self.budynek_id_map:
            self.budynek_var.set(aktualna_nazwa)
        elif nazwy_budynkow:
            # jeśli obecnego nie ma (np. dopiero dodany pierwszy budynek)
            self.budynek_var.set(nazwy_budynkow[0])
            # zsynchronizuj self.budynek z wybraną nazwą
            self._zmien_budynek_po_nazwie(nazwy_budynkow[0])

        # odśwież tabelę przeglądów dla aktualnego budynku
        if hasattr(self, "tabela_przeglady") and self.tabela_przeglady is not None:
            self.odswiez_przeglady()


    def odswiez_konta(self):
        """Odświeża listę kont w zakładce admina (z zapisem do _wszystkie_konta)."""
        if not hasattr(self, "tabela_konta"):
            return

        self._wszystkie_konta = []
        self.konta_map.clear()

        try:
            wiersze = lista_uzytkownikow_szczegoly()
        except Exception as e:
            messagebox.showerror(
                "Błąd", f"Nie udało się pobrać listy kont:\n{e}"
            )
            return

        for row in wiersze:
            (
                uid,
                login,
                haslo,
                rola,
                _budynek_nazwa,  # nie używamy bezpośrednio
                budynek_id,
                ostatnie_log,
            ) = row

            # hasło – ukryte dla ADMIN
            if rola == "ADMIN":
                haslo_podglad = "******"
            else:
                haslo_podglad = haslo or ""

            ostatnie = ostatnie_log or "(brak danych)"

            # opis budynków
            budynki = lista_budynkow_dla_uzytkownika(uid)  # [(id, nazwa), ...]
            if rola == "ADMIN":
                budynki_tekst = "Wszystkie budynki"
            else:
                if not budynki:
                    budynki_tekst = "(brak)"
                else:
                    nazwy = [n for (_bid, n) in budynki]
                    if len(nazwy) <= 3:
                        budynki_tekst = ", ".join(nazwy)
                    else:
                        budynki_tekst = f"{len(nazwy)} budynków"

            rec = {
                "uid": uid,
                "login": login,
                "haslo": haslo or "",
                "rola": rola,
                "budynek_id": budynek_id,
                "budynki_tekst": budynki_tekst,
                "ostatnie": ostatnie,
                "haslo_podglad": haslo_podglad,
            }
            self._wszystkie_konta.append(rec)

        # po zapełnieniu _wszystkie_konta stosujemy filtry + sort
        self._przelicz_i_wyswietl_konta()

    def _przelicz_i_wyswietl_konta(self):
        """Stosuje filtry i sortowanie na _wszystkie_konta i ładuje tabelę."""
        if not hasattr(self, "tabela_konta"):
            return

        # 1. FILTROWANIE
        wiersze = []
        for rec in getattr(self, "_wszystkie_konta", []):
            if self._pasuje_do_filtrow_konta(rec):
                wiersze.append(rec)

        # 2. SORTOWANIE (3-stanowe: brak / rosnąco / malejąco)
        kol = getattr(self, "_sort_konta_column", None)
        order = getattr(self, "_sort_konta_order", None)
        if kol and order:
            reverse = order == "desc"

            def klucz(rec):
                if kol == "ID":
                    return rec["uid"]
                if kol == "Login":
                    return rec["login"].lower()
                if kol == "Rola":
                    return rec["rola"]
                if kol.startswith("Budynek"):
                    return rec["budynki_tekst"]
                if kol.startswith("Ostatnie"):
                    return rec["ostatnie"] or ""
                return ""

            wiersze = sorted(wiersze, key=klucz, reverse=reverse)

        # 3. ZAŁADOWANIE DO TREEVIEW + uzupełnienie konta_map
        for item in self.tabela_konta.get_children():
            self.tabela_konta.delete(item)
        self.konta_map.clear()

        for rec in wiersze:
            item_id = self.tabela_konta.insert(
                "",
                "end",
                values=(
                    rec["uid"],
                    rec["login"],
                    rec["rola"],
                    rec["budynki_tekst"],
                    rec["ostatnie"],
                    rec["haslo_podglad"],
                ),
            )
            self.konta_map[item_id] = {
                "id": rec["uid"],
                "login": rec["login"],
                "haslo": rec["haslo"],
                "rola": rec["rola"],
                "budynek_id": rec["budynek_id"],
                "ostatnie_logowanie": rec["ostatnie"],
            }

    def _pasuje_do_filtrow_konta(self, rec):
        """Sprawdza, czy rekord konta spełnia aktualne ustawienia filtrów."""
        if not hasattr(self, "filter_konto_id_var"):
            return True

        fid = self.filter_konto_id_var.get().strip()
        if fid and fid not in str(rec["uid"]):
            return False

        flog = self.filter_konto_login_var.get().strip().lower()
        if flog and flog not in rec["login"].lower():
            return False

        frola = self.filter_konto_rola_var.get()
        if frola and frola != "(wszystkie)" and rec["rola"] != frola:
            return False

        fbud = self.filter_konto_budynek_var.get().strip().lower()
        if fbud and fbud not in rec["budynki_tekst"].lower():
            return False

        return True

    def _zastosuj_filtry_konta(self):
        """Wywoływane z pól filtrów – po prostu odświeża widok."""
        self._przelicz_i_wyswietl_konta()

    def _wyczysc_filtry_konta(self):
        """Czyści wszystkie filtry + resetuje sortowanie."""
        if hasattr(self, "filter_konto_id_var"):
            self.filter_konto_id_var.set("")
            self.filter_konto_login_var.set("")
            self.filter_konto_rola_var.set("(wszystkie)")
            self.filter_konto_budynek_var.set("")
        self._sort_konta_column = None
        self._sort_konta_order = None
        self._przelicz_i_wyswietl_konta()

    def _klik_naglowek_konta(self, kolumna):
        """Kliknięcie nagłówka w tabeli kont – sortowanie 3-stanowe."""
        # na wszelki wypadek, gdyby ktoś spróbował o hasło – ignorujemy
        if kolumna == "Hasło (podgląd)":
            return

        poprzednia = getattr(self, "_sort_konta_column", None)
        order = getattr(self, "_sort_konta_order", None)

        if poprzednia != kolumna:
            self._sort_konta_column = kolumna
            self._sort_konta_order = "asc"
        else:
            if order == "asc":
                self._sort_konta_order = "desc"
            elif order == "desc":
                # trzecie kliknięcie – wyłącz sortowanie
                self._sort_konta_column = None
                self._sort_konta_order = None
            else:
                self._sort_konta_order = "asc"

        self._przelicz_i_wyswietl_konta()

    def _ustaw_edycje_konta(self, aktywne, login_text):
        """
        Włącza/wyłącza pola do zmiany loginu/hasła w zakładce kont.
        """
        state = "normal" if aktywne else "disabled"
        if hasattr(self, "konto_nowy_login_entry"):
            self.konto_nowy_login_entry.configure(state=state)
            self.konto_nowe_haslo_entry.configure(state=state)
            self.btn_konto_zmien_dane.configure(state=state)

            self.konto_nowy_login_entry.delete(0, "end")
            self.konto_nowe_haslo_entry.delete(0, "end")

            if aktywne and login_text:
                self.konto_nowy_login_entry.insert(0, login_text)

    def _on_select_konto(self, _evt=None):
        sel = self.tabela_konta.focus()
        if not sel or sel not in self.konta_map:
            return
        info = self.konta_map[sel]
        self.aktualne_konto_id = info["id"]

        # login/hasło widoczne tylko dla PRACOWNIK/TECHNIK
        if info["rola"] == "ADMIN":
            self.lbl_konto_login.config(text="Login: (ukryty dla ADMIN)")
            self.lbl_konto_haslo.config(text="Hasło: (ukryte dla ADMIN)")
        else:
            self.lbl_konto_login.config(text=f"Login: {info['login']}")
            self.lbl_konto_haslo.config(text=f"Hasło: {info['haslo']}")

        self.lbl_konto_rola.config(text=f"Rola: {info['rola']}")
        self.lbl_konto_logowanie.config(
            text=f"Ostatnie logowanie: {info['ostatnie_logowanie']}"
        )

        # zaznaczenie budynków w listboxie
        self.lista_budynkow_konta.selection_clear(0, "end")

        # ADMIN – ma wszystkie budynki automatycznie, listy nie edytujemy,
        # i NIE może mieć zmienianego loginu/hasła
        if info["rola"] == "ADMIN":
            self.lista_budynkow_konta.config(state="disabled")
            self.btn_konto_zapisz.config(state="disabled")
            self._ustaw_edycje_konta(False, "")
            return

        # PRACOWNIK / TECHNIK – można edytować budynki
        self.lista_budynkow_konta.config(state="normal")
        self.btn_konto_zapisz.config(state="normal")

        przypisane = lista_budynkow_dla_uzytkownika(info["id"])  # [(id, nazwa)]
        przyp_ids = {bid for (bid, _n) in przypisane}

        for idx, (bid, _nazwa) in enumerate(self.budynki_lista):
            if bid in przyp_ids:
                self.lista_budynkow_konta.selection_set(idx)

        # edycja loginu/hasła tylko dla PRACOWNIK / TECHNIK
        if info["rola"] in ("PRACOWNIK", "TECHNIK"):
            self._ustaw_edycje_konta(True, info["login"])
        else:
            self._ustaw_edycje_konta(False, "")

        # przycisk "Edytuj użytkownika" aktywny tylko dla PRACOWNIK / TECHNIK
        if hasattr(self, "btn_edytuj_uzytkownika"):
            if info["rola"] in ("PRACOWNIK", "TECHNIK"):
                self.btn_edytuj_uzytkownika.config(state="normal")
            else:
                self.btn_edytuj_uzytkownika.config(state="disabled")
        # przycisk "Usuń użytkownika" też tylko dla PRACOWNIK / TECHNIK
        if hasattr(self, "btn_usun_uzytkownika"):
            if info["rola"] in ("PRACOWNIK", "TECHNIK"):
                self.btn_usun_uzytkownika.config(state="normal")
            else:
                self.btn_usun_uzytkownika.config(state="disabled")


    def _zapisz_budynek_konta(self):
        """Zapisuje wybrane budynki dla zaznaczonego konta (PRACOWNIK/TECHNIK)."""
        if not hasattr(self, "aktualne_konto_id"):
            messagebox.showwarning("Brak wyboru", "Najpierw wybierz konto z listy.")
            return

        # znajdujemy dane wybranego konta
        konto = None
        for info in self.konta_map.values():
            if info["id"] == self.aktualne_konto_id:
                konto = info
                break

        if konto is None:
            messagebox.showerror("Błąd", "Nie udało się znaleźć danych konta.")
            return

        if konto["rola"] == "ADMIN":
            messagebox.showinfo(
                "Informacja",
                "Konto ADMIN ma przypisane wszystkie budynki automatycznie.\n"
                "Nie można ręcznie zmieniać budynków dla konta ADMIN."
            )
            return

        zaznaczone = self.lista_budynkow_konta.curselection()
        bud_ids = [self.budynki_lista[i][0] for i in zaznaczone]

        try:
            ustaw_budynki_dla_uzytkownika(self.aktualne_konto_id, bud_ids)
        except Exception as e:
            messagebox.showerror(
                "Błąd", f"Nie udało się zapisać przypisanych budynków:\n{e}"
            )
            return

        messagebox.showinfo("OK", "Przypisane budynki zostały zaktualizowane.")
        self.odswiez_konta()

    def _usun_budynki_konta(self):
        """
        Odbiera WSZYSTKIE budynki od aktualnie zaznaczonego konta
        (PRACOWNIK / TECHNIK).
        """
        if not hasattr(self, "aktualne_konto_id"):
            messagebox.showwarning(
                "Brak wyboru",
                "Najpierw wybierz konto z listy."
            )
            return

        # znajdź dane wybranego konta
        konto = None
        for info in self.konta_map.values():
            if info["id"] == self.aktualne_konto_id:
                konto = info
                break

        if konto is None:
            messagebox.showerror("Błąd", "Nie udało się znaleźć danych konta.")
            return

        if konto["rola"] == "ADMIN":
            messagebox.showinfo(
                "Informacja",
                "Konto ADMIN ma przypisane wszystkie budynki automatycznie.\n"
                "Nie można ręcznie usuwać budynków z konta ADMIN."
            )
            return

        if not messagebox.askyesno(
            "Potwierdź",
            f"Czy na pewno chcesz odebrać wszystkie budynki "
            f"użytkownikowi '{konto['login']}'?"
        ):
            return

        try:
            # pusta lista = brak przypisanych budynków
            ustaw_budynki_dla_uzytkownika(self.aktualne_konto_id, [])
        except Exception as e:
            messagebox.showerror(
                "Błąd",
                f"Nie udało się zaktualizować przypisanych budynków:\n{e}"
            )
            return

        messagebox.showinfo(
            "OK",
            "Przypisania użytkownika zostały usunięte."
        )

        # odśwież widok kont + wyczyść zaznaczenia w liście budynków
        self.odswiez_konta()
        self.lista_budynkow_konta.selection_clear(0, "end")


    def _pokaz_okno_dodaj_budynek(self):
        """Okienko dodawania nowego budynku (ADMIN)."""
        # sprawdź, czy już otwarte
        if self.okno_dodaj_budynek is not None and self.okno_dodaj_budynek.winfo_exists():
            self.okno_dodaj_budynek.lift()
            self.okno_dodaj_budynek.focus_force()
            return

        okno = tk.Toplevel(self)
        self.okno_dodaj_budynek = okno
        okno.bind("<Destroy>", lambda e: setattr(self, "okno_dodaj_budynek", None))

        okno.title("Dodaj budynek")
        okno.resizable(False, False)
        okno.transient(self)
        okno.grab_set()
        try:
            okno.configure(bg=self["bg"])
        except Exception:
            pass
        okno.resizable(False, False)
        okno.transient(self)
        okno.grab_set()
        try:
            okno.configure(bg=self["bg"])
        except Exception:
            pass

        frm = ttk.Frame(okno, padding=10)
        frm.pack(fill="both", expand=True)

        # --- podstawowe dane ---
        ttk.Label(frm, text="Nazwa budynku:").grid(
            row=0, column=0, sticky="w", padx=4, pady=4
        )
        nazwa_entry = ttk.Entry(frm, width=30, style="Dark.TEntry")
        nazwa_entry.grid(row=0, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(frm, text="Ulica (opcjonalnie):").grid(
            row=1, column=0, sticky="w", padx=4, pady=4
        )
        ulica_entry = ttk.Entry(frm, width=30, style="Dark.TEntry")
        ulica_entry.grid(row=1, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(frm, text="Kod pocztowy (opcjonalnie):").grid(
            row=2, column=0, sticky="w", padx=4, pady=4
        )
        kod_entry = ttk.Entry(frm, width=15, style="Dark.TEntry")
        kod_entry.grid(row=2, column=1, sticky="w", padx=4, pady=4)

        # --- parametry techniczne budynku ---
        ttk.Label(frm, text="Liczba pięter:").grid(
            row=3, column=0, sticky="w", padx=4, pady=4
        )
        pieter_entry = ttk.Entry(frm, width=10, style="Dark.TEntry")
        pieter_entry.insert(0, "10")
        pieter_entry.grid(row=3, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(frm, text="Liczba wind:").grid(
            row=4, column=0, sticky="w", padx=4, pady=4
        )
        windy_entry = ttk.Entry(frm, width=10, style="Dark.TEntry")
        windy_entry.insert(0, "2")
        windy_entry.grid(row=4, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(frm, text="Wyjścia ewakuacyjne/p.poż na piętro:").grid(
            row=5, column=0, sticky="w", padx=4, pady=4
        )
        wyjscia_entry = ttk.Entry(frm, width=10, style="Dark.TEntry")
        wyjscia_entry.insert(0, "2")
        wyjscia_entry.grid(row=5, column=1, sticky="w", padx=4, pady=4)

        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=2, sticky="e", pady=(10, 0))

        def anuluj():
            okno.destroy()

        def potwierdz():
            nazwa = (nazwa_entry.get() or "").strip()
            ulica = (ulica_entry.get() or "").strip()
            kod = (kod_entry.get() or "").strip()
            lp_txt = (pieter_entry.get() or "").strip()
            lw_txt = (windy_entry.get() or "").strip()
            wyj_txt = (wyjscia_entry.get() or "").strip()

            if not nazwa:
                messagebox.showwarning("Brak nazwy", "Nazwa budynku jest wymagana.")
                return

            try:
                lp = int(lp_txt) if lp_txt else 10
                lw = int(lw_txt) if lw_txt else 2
                wyj = int(wyj_txt) if wyj_txt else 2
            except ValueError:
                messagebox.showwarning(
                    "Błąd danych",
                    "Liczba pięter, wind i wyjść na piętro musi być liczbą całkowitą.",
                )
                return

            if lp <= 0 or lw <= 0 or wyj <= 0:
                messagebox.showwarning(
                    "Błędne wartości",
                    "Wszystkie wartości muszą być dodatnie.",
                )
                return

            try:
                dodaj_budynek(
                    nazwa,
                    ulica,
                    kod,
                    stan="",
                    opis="",
                    liczba_pieter=lp,
                    liczba_wind=lw,
                    wyjscia_na_pietro=wyj,
                )
            except Exception as e:
                messagebox.showerror(
                    "Błąd",
                    f"Nie udało się dodać budynku:\n{e}",
                )
                return

            messagebox.showinfo("OK", "Budynek został dodany.")
            okno.destroy()
            self._zaladuj_budynki_do_kont()
            self.odswiez_konta()
            self._odswiez_budynki_admin()

        btn_ok = ttk.Button(btns, text="Potwierdź", command=potwierdz)
        btn_ok.pack(side="right", padx=4)
        btn_cancel = ttk.Button(btns, text="Anuluj", command=anuluj)
        btn_cancel.pack(side="right", padx=4)

        frm.columnconfigure(1, weight=1)
        nazwa_entry.focus_set()
        self._wycentruj_okno(okno)

    def _otworz_okno_edycji_konta(self, event=None):
        """
        Podwójny klik na użytkowniku w tabeli:
        otwiera okno do zmiany loginu i (opcjonalnie) hasła.
        Tylko dla ról PRACOWNIK / TECHNIK.
        """
        # ustalamy, który wiersz został kliknięty
        if event is not None:
            item_id = self.tabela_konta.identify_row(event.y)
        else:
            item_id = self.tabela_konta.focus()

        if not item_id or item_id not in self.konta_map:
            return

        info = self.konta_map[item_id]  # dict z danymi konta

        if info["rola"] == "ADMIN":
            messagebox.showwarning(
                "Brak uprawnień",
                "Nie można zmieniać loginu/hasła kont typu ADMIN.",
            )
            return

        # === tworzenie okna – tylko jedna instancja ===
        if self.okno_edycja_konta is not None and self.okno_edycja_konta.winfo_exists():
            self.okno_edycja_konta.lift()
            self.okno_edycja_konta.focus_force()
            return

        okno = tk.Toplevel(self)
        self.okno_edycja_konta = okno
        okno.bind("<Destroy>", lambda e: setattr(self, "okno_edycja_konta", None))

        okno.title(f"Zmiana loginu/hasła – {info['login']}")
        okno.transient(self)
        okno.grab_set()
        okno.resizable(False, False)


        # === kolory z motywu ===
        if self.tryb_ciemny:
            bg = "#1e293b"
            fg = "#f0f0f0"
            pole = "#3a3a3a"
            naglowek = "#444444"
        else:
            bg = "#f0f0f0"
            fg = "#000000"
            pole = "#ffffff"
            naglowek = "#e0e0e0"

        # ustawienia tła okna
        okno.configure(bg=bg)

        # ====== WIDŻETY =======

        # Etykieta tytułu
        lbl_title = ttk.Label(
            okno,
            text=f"Użytkownik: {info['login']} (rola: {info['rola']})",
        )
        lbl_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 4))

        # Nowy login
        ttk.Label(okno, text="Nowy login:").grid(
            row=1, column=0, sticky="w", padx=10, pady=4
        )
        login_var = tk.StringVar(value=info["login"])
        entry_login = tk.Entry(okno, textvariable=login_var, bg=pole, fg=fg, insertbackground=fg)
        entry_login.grid(row=1, column=1, sticky="we", padx=10, pady=4)

        # Nowe hasło
        ttk.Label(okno, text="Nowe hasło (opcjonalne):").grid(
            row=2, column=0, sticky="w", padx=10, pady=4
        )
        haslo_var = tk.StringVar()
        entry_haslo = tk.Entry(okno, textvariable=haslo_var, show="*", bg=pole, fg=fg, insertbackground=fg)
        entry_haslo.grid(row=2, column=1, sticky="we", padx=10, pady=4)

        # === przycisk zapisu ===
        def zapisz():
            nowy_login = login_var.get().strip()
            nowe_haslo = haslo_var.get().strip()

            if not nowy_login:
                messagebox.showwarning("Błąd", "Login nie może być pusty.", parent=okno)
                return

            if nowe_haslo and len(nowe_haslo) < 4:
                messagebox.showwarning(
                    "Błąd",
                    "Hasło powinno mieć co najmniej 4 znaki.",
                    parent=okno,
                )
                return

            try:
                ok = ustaw_login_haslo_dla_uzytkownika(
                    info["id"],
                    nowy_login,
                    nowe_haslo or None,
                )
            except ValueError as e:
                messagebox.showerror("Błąd", str(e), parent=okno)
                return
            except Exception as e:
                messagebox.showerror(
                    "Błąd",
                    f"Nie udało się zaktualizować danych konta:\n{e}",
                    parent=okno,
                )
                return

            messagebox.showinfo(
                "OK", "Dane konta zostały zaktualizowane.", parent=okno
            )
            okno.destroy()
            self.odswiez_konta()

        # ENTER = zapis
        entry_haslo.bind("<Return>", lambda _e: zapisz())

        # === przyciski ===
        btn_zapisz = ttk.Button(okno, text="Zapisz", command=zapisz)
        btn_anuluj = ttk.Button(okno, text="Anuluj", command=okno.destroy)

        btn_zapisz.grid(row=3, column=0, sticky="e", padx=10, pady=10)
        btn_anuluj.grid(row=3, column=1, sticky="w", padx=10, pady=10)

        okno.columnconfigure(1, weight=1)
        entry_login.focus_set()

        self._wycentruj_okno(okno)

    def _dodaj_nowy_budynek_admin(self):
        """
        Dodaje nowy budynek do bazy (tylko ADMIN – bo tylko on ma tę zakładkę).
        Po dodaniu odświeża listę budynków w listboxie oraz listę kont.
        """
        nazwa = self.budynek_nazwa_entry.get().strip()
        ulica = self.budynek_ulica_entry.get().strip()
        kod = self.budynek_kod_entry.get().strip()

        if not nazwa:
            messagebox.showwarning("Błąd", "Podaj nazwę budynku.")
            return

        try:
            bid = dodaj_budynek(nazwa, ulica, kod, stan="", opis="")
        except ValueError as e:
            messagebox.showwarning("Błąd", str(e))
            return
        except Exception as e:
            messagebox.showerror(
                "Błąd",
                f"Nie udało się dodać budynku:\n{e}",
            )
            return

        # czyścimy pola
        self.budynek_nazwa_entry.delete(0, "end")
        self.budynek_ulica_entry.delete(0, "end")
        self.budynek_kod_entry.delete(0, "end")

        messagebox.showinfo(
            "OK",
            f"Dodano nowy budynek (ID: {bid}).\nMożesz teraz przypisać go do kont.",
        )

        # odśwież listę budynków w comboboxach / listboxie
        self._zaladuj_budynki_do_kont()
        self.odswiez_konta()

    def _pokaz_historie_przegladu(self, _evt=None):
        """
        Dwuklik w wiersz tabeli przeglądów – otwiera okno z historią
        przeglądów danego typu. Dla ADMINA umożliwia edycję/usuwanie
        pojedynczych wpisów.
        """
        if not self.budynek or not self.tabela_przeglady:
            return

        sel = self.tabela_przeglady.focus()
        if not sel:
            return
        wartosci = self.tabela_przeglady.item(sel)["values"]
        if not wartosci:
            return

        nazwa_typu = wartosci[0]
        typ = PRZEGLADY_NAZWY_ODWROTNIE.get(nazwa_typu, nazwa_typu)

        try:
            # teraz: lista (id, data_wizyty, technik, uwagi)
            wiersze = historia_przegladow_dla_budynku_i_typu(
                self.budynek["id"], typ
            )
        except Exception as e:
            messagebox.showerror(
                "Błąd",
                f"Nie udało się pobrać historii przeglądów:\n{e}",
            )
            return

        # jeśli jakieś okno historii już istnieje – zamknij, żeby nie dublować
        if getattr(self, "okno_historia_przegladu", None) is not None:
            if self.okno_historia_przegladu.winfo_exists():
                self.okno_historia_przegladu.destroy()

        okno = tk.Toplevel(self)
        self.okno_historia_przegladu = okno
        okno.bind(
            "<Destroy>",
            lambda e: setattr(self, "okno_historia_przegladu", None),
        )

        colors = get_colors()
        try:
            okno.configure(bg=colors["bg"])
        except Exception:
            pass

        okno.title(f"Historia przeglądów – {nazwa_typu}")
        okno.geometry("650x420")
        okno.transient(self)
        okno.grab_set()
        self._wycentruj_okno(okno)

        # --------- główna ramka ----------
        frame = ttk.Frame(okno, padding=8)
        frame.pack(fill="both", expand=True)

        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        kolumny = ("Data wizyty", "Technik", "Uwagi")
        tree = ttk.Treeview(
            frame,
            columns=kolumny,
            show="headings",
            height=12,
        )
        for k in kolumny:
            tree.heading(k, text=k)

        tree.column("Data wizyty", width=110, anchor="center")
        tree.column("Technik", width=160, anchor="w")
        tree.column("Uwagi", width=320, anchor="w")
        tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)

        for pid, data_wizyty, technik, uwagi in wiersze:
            tree.insert(
                "",
                "end",
                iid=str(pid),  # WAŻNE: ID przeglądu jako identyfikator wiersza
                values=(data_wizyty, technik, uwagi or ""),
            )

        if not wiersze:
            ttk.Label(
                frame,
                text="Brak zarejestrowanych przeglądów tego typu.",
            ).grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=4)

        # --------- przyciski ADMINA: edycja/usuwanie ----------
        if self.uzytkownik.get("rola") == "ADMIN":

            def _pobierz_wybrany():
                sel_id = tree.focus()
                if not sel_id:
                    messagebox.showwarning(
                        "Brak wyboru", "Najpierw zaznacz przegląd na liście.",
                        parent=okno,
                    )
                    return None, None
                try:
                    pid = int(sel_id)
                except ValueError:
                    return None, None
                values = tree.item(sel_id)["values"]
                if not values or len(values) < 3:
                    return None, None
                data_wizyty, technik, uwagi = values
                return pid, (data_wizyty, technik, uwagi)

            def _edytuj():
                pid, dane = _pobierz_wybrany()
                if pid is None:
                    return
                data_wizyty, technik, uwagi = dane

                ew = tk.Toplevel(okno)
                ew.title("Edytuj przegląd")
                ew.transient(okno)
                ew.grab_set()
                try:
                    ew.configure(bg=colors["bg"])
                except Exception:
                    pass

                frm = ttk.Frame(ew, padding=10)
                frm.pack(fill="both", expand=True)

                ttk.Label(frm, text="Data wizyty (RRRR-MM-DD):").grid(
                    row=0, column=0, sticky="w", padx=4, pady=4
                )
                entry_data = ttk.Entry(frm, width=16, style="Dark.TEntry")
                entry_data.grid(row=0, column=1, sticky="w", padx=4, pady=4)
                entry_data.insert(0, data_wizyty)

                ttk.Label(frm, text="Technik:").grid(
                    row=1, column=0, sticky="w", padx=4, pady=4
                )
                entry_technik = ttk.Entry(frm, width=24, style="Dark.TEntry")
                entry_technik.grid(row=1, column=1, sticky="w", padx=4, pady=4)
                entry_technik.insert(0, technik)

                ttk.Label(frm, text="Uwagi:").grid(
                    row=2, column=0, sticky="nw", padx=4, pady=4
                )
                entry_uwagi = ttk.Entry(frm, width=40, style="Dark.TEntry")
                entry_uwagi.grid(row=2, column=1, sticky="we", padx=4, pady=4)
                entry_uwagi.insert(0, uwagi)

                btns = ttk.Frame(frm)
                btns.grid(row=3, column=0, columnspan=2, sticky="e", pady=(8, 0))

                def zapisz():
                    nowa_data = entry_data.get().strip()
                    nowy_technik = entry_technik.get().strip()
                    nowe_uwagi = entry_uwagi.get().strip() or None

                    if not nowa_data or not nowy_technik:
                        messagebox.showwarning(
                            "Błąd",
                            "Data wizyty i technik są wymagane.",
                            parent=ew,
                        )
                        return

                    # prosta walidacja daty
                    try:
                        datetime.date.fromisoformat(nowa_data)
                    except ValueError:
                        messagebox.showwarning(
                            "Błąd",
                            "Niepoprawny format daty. Użyj RRRR-MM-DD.",
                            parent=ew,
                        )
                        return

                    try:
                        ok = edytuj_przeglad_techniczny(
                            pid, nowa_data, nowy_technik, nowe_uwagi
                        )
                    except Exception as exc:
                        messagebox.showerror(
                            "Błąd",
                            f"Nie udało się zaktualizować przeglądu:\n{exc}",
                            parent=ew,
                        )
                        return

                    if not ok:
                        messagebox.showerror(
                            "Błąd",
                            "Nie znaleziono przeglądu w bazie.",
                            parent=ew,
                        )
                        return

                    # podmień wartości w tabeli
                    tree.item(str(pid), values=(nowa_data, nowy_technik, nowe_uwagi or ""))
                    ew.destroy()
                    self.odswiez_przeglady()

                ttk.Button(btns, text="Zapisz", command=zapisz).pack(
                    side="right", padx=4
                )
                ttk.Button(btns, text="Anuluj", command=ew.destroy).pack(
                    side="right", padx=4
                )

                frm.columnconfigure(1, weight=1)
                entry_data.focus_set()
                self._wycentruj_okno(ew)

            def _usun():
                pid, _ = _pobierz_wybrany()
                if pid is None:
                    return
                if not messagebox.askyesno(
                    "Potwierdź usunięcie",
                    "Czy na pewno chcesz trwale usunąć wybrany przegląd?",
                    parent=okno,
                ):
                    return
                try:
                    ok = usun_przeglad_techniczny(pid)
                except Exception as exc:
                    messagebox.showerror(
                        "Błąd",
                        f"Nie udało się usunąć przeglądu:\n{exc}",
                        parent=okno,
                    )
                    return

                if not ok:
                    messagebox.showerror(
                        "Błąd",
                        "Nie znaleziono przeglądu w bazie.",
                        parent=okno,
                    )
                    return

                tree.delete(str(pid))
                self.odswiez_przeglady()

                if not tree.get_children():
                    ttk.Label(
                        frame,
                        text="Brak zarejestrowanych przeglądów tego typu.",
                    ).grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=4)

            btns_bottom = ttk.Frame(frame)
            btns_bottom.grid(row=2, column=0, columnspan=2, sticky="e", pady=(6, 0))

            btn_usun = ttk.Button(btns_bottom, text="Usuń wybrany", command=_usun)
            btn_usun.pack(side="right", padx=4)

            btn_edytuj = ttk.Button(btns_bottom, text="Edytuj wybrany", command=_edytuj)
            btn_edytuj.pack(side="right", padx=4)



    # ---------- Zegar globalny i czas sesji ----------
    def _aktualizuj_czas(self):
        if self.lbl_czas_globalny and self.lbl_czas_sesji:
            teraz = datetime.datetime.now()  # zakładamy, że system ma czas Warszawy
            self.lbl_czas_globalny.config(
                text="Czas (Warszawa): " + teraz.strftime("%Y-%m-%d %H:%M:%S")
            )

            delta = teraz - self.session_start
            sek = int(delta.total_seconds())
            h = sek // 3600
            m = (sek % 3600) // 60
            s = sek % 60
            self.lbl_czas_sesji.config(text=f"Sesja: {h:02d}:{m:02d}:{s:02d}")

        # odśwież co 1 sekundę
        self._after_czas = self.after(1000, self._aktualizuj_czas)

    # ---------- Symulatory losowych danych ----------
    def _krok_windy(
        self,
        floor,
        target,
        direction,
        speed,
        wait,
        min_floor=0,
        max_floor=15,
    ):
        """
        Symuluje jeden krok czasu dla windy.
        Zwraca: floor, target, direction, speed, wait, moving, speed_now.
        """
        # jeśli winda stoi na piętrze i nie ma zaplanowanego postoju ani celu – wybierz nowy cel
        if direction == 0 and wait == 0 and floor == target:
            new_target = random.randint(min_floor, max_floor)
            while new_target == floor:
                new_target = random.randint(min_floor, max_floor)
            target = new_target
            direction = 1 if target > floor else -1
            speed = random.uniform(0.6, 2.0)  # stała prędkość na cały przejazd

        # jeśli ma jeszcze postój – odliczaj
        if wait > 0:
            wait -= 1
            moving = False
            speed_now = 0.0
            return floor, target, direction, speed, wait, moving, speed_now

        # jeśli dojechała do celu
        if floor == target:
            # krótki postój 1–3 tiku
            wait = random.randint(1, 3)
            direction = 0
            moving = False
            speed_now = 0.0
            return floor, target, direction, speed, wait, moving, speed_now

        # winda jedzie o jedno piętro w kierunku celu
        floor += 1 if direction > 0 else -1
        floor = max(min_floor, min(max_floor, floor))
        moving = True
        speed_now = speed

        return floor, target, direction, speed, wait, moving, speed_now

    def _start_symulatory(self):
        """Uruchamia cykliczną aktualizację losowych danych na pulpicie."""
        # symulatory mają działać dla PRACOWNIKA i TECHNIKA
        if self.uzytkownik["rola"] not in ("PRACOWNIK", "TECHNIK"):
            return
        self._aktualizuj_symulatory()

    def _aktualizuj_symulatory(self):
        # symulatory tylko dla PRACOWNIKA i TECHNIKA
        if self.uzytkownik["rola"] not in ("PRACOWNIK", "TECHNIK"):
            return

        # ile pięter ma budynek – do ograniczenia ruchu wind
        max_floor = 10
        if self.budynek:
            try:
                lp = int(self.budynek.get("liczba_pieter", 10))
                # piętra liczymy od 0, więc max_floor to lp-1
                max_floor = max(0, lp)
            except (TypeError, ValueError):
                max_floor = 10

        # ----- Stan sieci -----
        if self.lbl_net:
            down = random.uniform(80, 200)  # Mb/s
            up = random.uniform(10, 60)  # Mb/s
            p = random.random()
            if p < 0.8:
                status = "OK"
            elif p < 0.95:
                status = "Wysokie obciążenie"
            else:
                status = "Awaria częściowa"
            self.lbl_net.config(
                text=f"Stan sieci: ↓ {down:5.1f} Mb/s, ↑ {up:5.1f} Mb/s ({status})"
            )

            # ----- Windy (dowolna liczba) -----
            # etykiety, które mamy na pulpicie
            if hasattr(self, "lbl_elevators") and self.lbl_elevators:
                labels = self.lbl_elevators
            else:
                # stary tryb – tylko dwie windy
                labels = [self.lbl_elev1, self.lbl_elev2]

            for idx, winda in enumerate(self.elevators):
                (
                    winda["floor"],
                    winda["target"],
                    winda["dir"],
                    winda["speed"],
                    winda["wait"],
                    moving,
                    speed_now,
                ) = self._krok_windy(
                    winda["floor"],
                    winda["target"],
                    winda["dir"],
                    winda["speed"],
                    winda["wait"],
                    min_floor=0,
                    max_floor=max_floor,
                )

                # aktualizacja tekstu tylko jeśli mamy etykietę dla tej windy
                if idx < len(labels) and labels[idx]:
                    if moving:
                        kier = "↑" if winda["dir"] > 0 else "↓"
                        ruch_txt = "jedzie"
                    else:
                        kier = "–"
                        ruch_txt = "stoi"

                    labels[idx].config(
                        text=(
                            f"Winda {idx + 1}: piętro {winda['floor']}, "
                            f"{speed_now:3.1f} m/s ({kier}, {ruch_txt})"
                        )
                    )

        # ----- Liczniki -----
        if self.lbl_power:
            moc = random.uniform(120, 180)  # kW
            self.lbl_power.config(text=f"Pobór prądu: {moc:6.1f} kW")
        if self.lbl_water:
            woda = random.uniform(0.0, 5.0)  # m³/h
            self.lbl_water.config(text=f"Pobór wody: {woda:4.2f} m³/h")

        # ----- Wyjścia ewakuacyjne -----
        if self.tabela_wyjsc and self.wyjscia:
            # (reszta Twojego istniejącego kodu dla wyjść zostaje BEZ zmian)
            for item in self.tabela_wyjsc.get_children():
                self.tabela_wyjsc.delete(item)

            if not hasattr(self, "_wyjscia_status"):
                self._wyjscia_status = {}

            now = datetime.datetime.now()
            podsumowanie = {}  # pietro -> (zamknięte, wszystkie)

            for pietro, nazwa in self.wyjscia:
                key = (pietro, nazwa)
                info = self._wyjscia_status.get(key)

                if info is None:
                    status = random.choice(["Zamknięte", "Otwarte"])
                    info = {
                        "status": status,
                        "last_change": now,
                    }
                    self._wyjscia_status[key] = info
                else:
                    status = info["status"]
                    elapsed = (now - info["last_change"]).total_seconds()
                    if elapsed >= 5.0:
                        new_status = random.choice(["Zamknięte", "Otwarte"])
                        if new_status != status:
                            status = new_status
                            info["status"] = status
                            info["last_change"] = now

                self.tabela_wyjsc.insert("", "end", values=(pietro, nazwa, status))

                if pietro not in podsumowanie:
                    podsumowanie[pietro] = [0, 0]
                if status == "Zamknięte":
                    podsumowanie[pietro][0] += 1
                podsumowanie[pietro][1] += 1

            tekst_podsum = []
            for pietro, (zamk, wszystkie) in sorted(podsumowanie.items()):
                tekst_podsum.append(
                    f"Piętro {pietro}: {zamk}/{wszystkie} zamkniętych"
                )
            if self.lbl_wyjscia_podsum:
                self.lbl_wyjscia_podsum.config(
                    text="Podsumowanie wyjść: " + ", ".join(tekst_podsum)
                )

        # zaplanuj kolejne odświeżenie
        self._after_symul = self.after(1000, self._aktualizuj_symulatory)

    # ---------- Wylogowanie ----------
    def _wyloguj(self):
        """Wylogowanie – anuluj timery i zamknij okno."""
        # anuluj timery, jeśli są zaplanowane
        for attr in ("_after_symul", "_after_czas"):
            after_id = getattr(self, attr, None)
            if after_id is not None:
                try:
                    self.after_cancel(after_id)
                except Exception:
                    pass
                setattr(self, attr, None)

        self.chce_wylogowac = True
        self.destroy()

    # ---------- Reszta: zgłoszenia / lista / szczegóły ----------
    def _wybierz_zdjecia(self):
        pliki = filedialog.askopenfilenames(
            title="Wybierz zdjęcia",
            filetypes=[("Obrazy", "*.jpg *.jpeg *.png *.bmp *.gif")]
        )
        if pliki:
            self.sciezki_zdjec = list(pliki)
            self.label_zdjecia.config(text=f"Wybrano {len(pliki)} plików")
        else:
            self.label_zdjecia.config(text="Brak wybranych plików")

    def _zapisz_zgloszenie(self):
        tytul = self.tytul_entry.get().strip()
        opis = self.opis_text.get("1.0", "end").strip()

        if not tytul:
            messagebox.showwarning("Błąd", "Tytuł zgłoszenia jest wymagany.")
            return

        # --- ustalenie ID budynku ---
        if self.uzytkownik.get("rola") == "ADMIN":
            bud_id = None
            if getattr(self, "zgl_budynek_var", None) is not None:
                nazwa_bud = (self.zgl_budynek_var.get() or "").strip()
                if nazwa_bud:
                    bud_id = self.zgl_budynek_id_map.get(nazwa_bud)

            if bud_id is None:
                messagebox.showwarning(
                    "Błąd",
                    "Wybierz budynek, do którego ma trafić zgłoszenie.",
                )
                return
        else:
            # PRACOWNIK / TECHNIK – zgłoszenie do aktualnie przypisanego budynku
            bud_id = self.budynek["id"] if self.budynek else None
            if bud_id is None:
                messagebox.showwarning(
                    "Błąd",
                    "Brak przypisanego budynku – nie można zapisać zgłoszenia.",
                )
                return

        try:
            priorytet = "NORMAL"
            kategoria = self.kategoria_var.get() or None

            dodaj_zgloszenie(
                tytul,
                opis,
                self.sciezki_zdjec,
                uzytkownik_id=self.uzytkownik["id"],
                budynek_id=bud_id,
                priorytet=priorytet,
                kategoria=kategoria,
            )

            # wyczyszczenie formularza
            self.tytul_entry.delete(0, "end")
            self.opis_text.delete("1.0", "end")
            self.label_zdjecia.config(text="Brak wybranych plików")
            self.sciezki_zdjec = []

            # odświeżenie widoków
            self.odswiez_liste()
            self.odswiez_pulpit()

            messagebox.showinfo("Sukces", "Zgłoszenie zapisano.")
        except Exception as e:
            messagebox.showerror("Błąd", str(e))

    def odswiez_liste(self):
        """Odświeża listę zgłoszeń (pobiera z bazy i stosuje filtry + sortowanie)."""
        if not hasattr(self, "tabela") or self.tabela is None:
            return

        try:
            # ADMIN widzi wszystkie zgłoszenia,
            # pozostali użytkownicy tylko dla swojego budynku
            if self.uzytkownik.get("rola") == "ADMIN":
                # WAŻNE: wersja z nazwą budynku jako ostatnią kolumną
                self._wszystkie_zgloszenia = lista_zgloszen_z_budynkiem()
            else:
                if self.budynek:
                    self._wszystkie_zgloszenia = lista_zgloszen(self.budynek["id"])
                else:
                    # konto bez przypisanego budynku – nic nie pokazujemy
                    self._wszystkie_zgloszenia = []

        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się pobrać listy zgłoszeń:\n{e}")
            self._wszystkie_zgloszenia = []
            return

        self._przelicz_i_wyswietl()

    def _przelicz_i_wyswietl(self):
        """Stosuje aktualne filtry i sortowanie na _wszystkie_zgloszenia i ładuje tabelę."""
        if not hasattr(self, "tabela") or self.tabela is None:
            return

        # 1. FILTROWANIE
        wiersze = []
        for r in getattr(self, "_wszystkie_zgloszenia", []):
            if self._pasuje_do_filtrow(r):
                wiersze.append(r)

        # 2. SORTOWANIE (3-stanowe: brak / rosnąco / malejąco)
        if self._sort_column and self._sort_order:
            idx = self._map_kolumn_index.get(self._sort_column)
            if idx is not None:
                reverse = self._sort_order == "desc"

                def klucz(r):
                    val = r[idx]
                    if self._sort_column in ("ID", "Zdjęcia"):
                        try:
                            return int(val)
                        except Exception:
                            return 0
                    else:
                        return str(val) if val is not None else ""

                wiersze = sorted(wiersze, key=klucz, reverse=reverse)

        # 3. ZAŁADOWANIE DO TREEVIEW
        for item in self.tabela.get_children():
            self.tabela.delete(item)

        for i, row in enumerate(wiersze):
            self.tabela.insert("", "end", values=row)

    def _pasuje_do_filtrow(self, r):
        """
        Sprawdza, czy wiersz r spełnia aktualne ustawienia filtrów.
        r: (id, tytul, status, priorytet, kategoria, zdjecia, utworzono, zaktualizowano)
        """
        # jeśli filtry nie są jeszcze zainicjalizowane – nic nie filtrujemy
        if not hasattr(self, "filter_status_var"):
            return True

        id_val = str(r[0])
        tytul_val = (r[1] or "")
        status_val = r[2]
        priorytet_val = r[3]
        kategoria_val = r[4]
        utworzono_val = r[6] or ""
        zaktualizowano_val = r[7] or ""
        budynek_val = r[8] if len(r) > 8 and r[8] is not None else ""


        # --- Status ---
        fs = self.filter_status_var.get()
        if fs and fs != "(wszystkie)" and status_val != fs:
            return False

        # --- Priorytet ---
        fp = self.filter_priorytet_var.get()
        if fp and fp != "(wszystkie)" and priorytet_val != fp:
            return False

        # --- Kategoria ---
        fk = self.filter_kategoria_var.get()
        if fk and fk != "(wszystkie)" and kategoria_val != fk:
            return False

        # --- Tytuł zawiera ---
        ft = self.filter_tytul_var.get().strip().lower()
        if ft and ft not in tytul_val.lower():
            return False

        # --- Budynek zawiera (tylko ADMIN) ---
        if hasattr(self, "filter_budynek_var"):
            fb = self.filter_budynek_var.get().strip().lower()
            if fb and fb not in budynek_val.lower():
                return False

        # --- ID zawiera ---
        fid = self.filter_id_var.get().strip()
        if fid and fid not in id_val:
            return False

        # --- Filtr daty ---
        kol_data = self.filter_data_kolumna_var.get()
        data_od = self.filter_data_od_var.get().strip()
        data_do = self.filter_data_do_var.get().strip()

        if kol_data in ("Utworzono", "Zaktualizowano") and (data_od or data_do):
            wartosc = utworzono_val if kol_data == "Utworzono" else zaktualizowano_val
            # w bazie format ISO: "RRRR-MM-DDTHH:MM:SSZ" – bierzemy tylko część daty
            data_wiersza = wartosc[:10] if wartosc else ""

            if data_od and data_wiersza < data_od:
                return False
            if data_do and data_wiersza > data_do:
                return False

        return True


    def _zastosuj_filtry(self):
        """Przelicza listę po zmianie filtrów."""
        self._przelicz_i_wyswietl()


    def _wyczysc_filtry(self):
        """Resetuje wszystkie filtry i sortowanie."""
        if hasattr(self, "filter_status_var"):
            self.filter_status_var.set("(wszystkie)")
            self.filter_priorytet_var.set("(wszystkie)")
            self.filter_kategoria_var.set("(wszystkie)")
            self.filter_tytul_var.set("")
            self.filter_id_var.set("")
            self.filter_data_kolumna_var.set("(brak)")
            self.filter_data_od_var.set("")
            self.filter_data_do_var.set("")
            if hasattr(self, "filter_budynek_var"):
                self.filter_budynek_var.set("")

        # sortowanie też zerujemy
        self._sort_column = None
        self._sort_order = None
        self._przelicz_i_wyswietl()


    def _klik_naglowek_listy(self, kolumna):
        """
        Obsługa kliknięcia w nagłówek tabeli.
        Dla wybranych kolumn: ID, Tytuł, Zdjęcia, Utworzono, Zaktualizowano, Budynek
        działa sortowanie 3-stanowe:
        1. brak → rosnąco
        2. rosnąco → malejąco
        3. malejąco → brak (powrót do naturalnego porządku – wg utworzono DESC + filtry).
        """
        if kolumna not in ("ID", "Tytuł", "Zdjęcia", "Utworzono", "Zaktualizowano", "Budynek"):
            return

        if self._sort_column != kolumna:
            # nowa kolumna – start od rosnącego
            self._sort_column = kolumna
            self._sort_order = "asc"
        else:
            # cykl: asc → desc → None
            if self._sort_order == "asc":
                self._sort_order = "desc"
            elif self._sort_order == "desc":
                self._sort_column = None
                self._sort_order = None
            else:
                self._sort_order = "asc"

        self._przelicz_i_wyswietl()

    def _pokaz_szczegoly(self, _evt=None):
        sel = self.tabela.focus()
        if not sel:
            return
        zgl_id = self.tabela.item(sel)["values"][0]
        self._otworz_okno_szczegolow(zgl_id)


    def _otworz_okno_szczegolow(self, zgl_id):
        dane, zdj = pobierz_zgloszenie(zgl_id)
        if not dane:
            messagebox.showerror("Błąd", "Nie znaleziono zgłoszenia.")
            return

        # jeśli okno szczegółów już istnieje – zamykamy je,
        # żeby mieć zawsze maksymalnie JEDNO okno tego typu
        if self.okno_szczegoly is not None and self.okno_szczegoly.winfo_exists():
            self.okno_szczegoly.destroy()
            self.okno_szczegoly = None

        self.okno_szczegoly = SzczegolyOkno(
            self,
            zgl_id,
            dane,
            zdj,
            lambda: (self.odswiez_liste(), self.odswiez_pulpit()),
        )

        # gdy okno zostanie zniszczone (X lub destroy),
        # czyścimy referencję
        self.okno_szczegoly.bind(
            "<Destroy>",
            lambda e: setattr(self, "okno_szczegoly", None)
        )


    def _pokaz_szczegoly_z_pulpitu(self, _evt=None):
        """Otwiera okno szczegółów po dwukliku na liście powiadomień (pulpit)."""
        if not self.tabela_powiad:
            return
        sel = self.tabela_powiad.focus()
        if not sel:
            return
        wartosci = self.tabela_powiad.item(sel)["values"]
        if not wartosci:
            return
        zgl_id = wartosci[0]

        self._otworz_okno_szczegolow(zgl_id)
