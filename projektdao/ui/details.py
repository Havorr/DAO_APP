import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from core import (
    ustaw_rozmiar_okna_procent,
    teraz_iso,
    polacz,
    pobierz_zgloszenie,
    pobierz_logi,
    dodaj_log,
    dodaj_zdjecia_do_zgloszenia,
    usun_zdjecie_ze_zgloszenia,
    zamknij_zgloszenie,
    przypisz_do_technika,
    ustaw_priorytet_zgloszenia,
    usun_zgloszenie,
    pobierz_przypisanego_technika,
    PRIORYTETY,
)
from ui.theme import get_colors   # <-- NOWY IMPORT


# -------------------- Okno szczegółów --------------------
class SzczegolyOkno(tk.Toplevel):
    def __init__(self, master, zgl_id, dane, zdj, on_change):
        super().__init__(master)

        self.transient(master)   # trzyma się nad oknem głównym
        self.grab_set()          # okno modalne – blokuje interakcję z tłem
        self.lift()              # na wierzch
        self.focus_force()       # fokus na tym oknie

        # kolory z motywu
        colors = get_colors()
        input_bg = colors.get("input_bg", colors.get("card_bg", "#1f2937"))
        # --- styl DarkTreeview dla logów ---
        style = ttk.Style(self)
        style.configure(
            "DarkTreeview",
            background=colors["card_bg"],
            fieldbackground=colors["card_bg"],
            foreground=colors["text"],
            bordercolor=colors["border"],
        )
        style.configure(
            "DarkTreeview.Heading",
            background=colors["card_bg"],
            foreground=colors["text"],
            bordercolor=colors["border"],
        )
        style.map(
            "DarkTreeview",
            background=[("selected", colors["accent"])],
            foreground=[("selected", "white")],
        )
        input_border = colors.get("input_border", colors.get("border", "#3b475c"))

        self.configure(bg=colors["bg"])
        self.title(f"Szczegóły zgłoszenia #{zgl_id}")
        ustaw_rozmiar_okna_procent(self, width_frac=0.8, height_frac=0.8, min_frac=0.5)
        self.resizable(True, True)

        # NAJPIERW zapamiętujemy referencję do głównej aplikacji
        self.master_app = master
        self.current_user_id = self.master_app.uzytkownik["id"]
        self.rola = self.master_app.uzytkownik["rola"]

        self.zgl_id = zgl_id
        self.dane = list(dane)
        self.on_change = on_change

        # kolumny: id, tytul, opis, status, utworzono, zaktualizowano,
        #          uzytkownik_id, budynek_id, priorytet, kategoria,
        #          przypisany_technik_id, zamkniete_przez
        self.owner_id = self.dane[6] if len(self.dane) > 6 else None
        self.status = self.dane[3]
        self.przypisany_technik_id = self.dane[10] if len(self.dane) > 10 else None
        self.zamkniete_przez = self.dane[11] if len(self.dane) > 11 else None

        # priorytet zgłoszenia (domyślnie NORMAL)
        self.priorytet = (
            self.dane[8] if len(self.dane) > 8 and self.dane[8] else "NORMAL"
        )

        # przyjmujemy prościej: każde DONE jest traktowane jako zamknięte
        self.czy_zamkniete = self.status == "DONE"

        self.czy_pracownik_moze_edytowac = (
            self.rola == "PRACOWNIK"
            and self.current_user_id == self.owner_id
            and self.status in ("OPEN", "IN_PROGRESS")
            and not self.czy_zamkniete
        )

        # TECHNIK: czy zgłoszenie jest przypisane do tego technika
        self.czy_technik_przypisany = (
            self.rola == "TECHNIK"
            and self.przypisany_technik_id == self.current_user_id
        )

        # TECHNIK zamykający
        self.czy_technik_zamykajacy = (
            self.rola == "TECHNIK"
            and self.zamkniete_przez == self.current_user_id
        )

        # TECHNIK może edytować opis DOPIERO po przejęciu zgłoszenia
        self.czy_technik_moze_edytowac_opis = (
            self.rola == "TECHNIK"
            and self.czy_technik_przypisany
            and not self.czy_zamkniete
        )

        # łączna flaga: kto w ogóle może edytować opis
        self.czy_moze_edytowac_opis = (
            self.czy_pracownik_moze_edytowac or self.czy_technik_moze_edytowac_opis
        )

        # === górne informacje ===
        top_frame = ttk.Frame(self, padding=10)
        top_frame.pack(fill="x")

        ttk.Label(top_frame, text=f"Tytuł: {self.dane[1]}").pack(anchor="w", pady=2)

        opis_frame = ttk.Frame(top_frame)
        opis_frame.pack(fill="x", pady=2)

        ttk.Label(opis_frame, text="Opis:").pack(anchor="nw", side="left")

        # --- pole opisu z ciemnym tłem + ramką ---
        self.opis_text = tk.Text(
            opis_frame,
            height=4,
            bg=input_bg,
            fg=colors["text"],
            insertbackground=colors["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=input_border,
            highlightcolor=colors["accent"],
            wrap="word",
        )
        self.opis_text.pack(fill="x", expand=True, side="left", padx=5)
        self.opis_text.insert("1.0", self.dane[2] or "")

        self.btn_zapisz_opis = ttk.Button(
            opis_frame,
            text="Zapisz opis",
            command=self._zapisz_opis,
        )
        self.btn_zapisz_opis.pack(side="right", padx=5)

        # status
        self.lbl_status = ttk.Label(top_frame, text=f"Status: {self.status}")
        self.lbl_status.pack(anchor="w", pady=2)

        # priorytet – edytowalny tylko dla TECHNIK/ADMIN
        priorytet_frame = ttk.Frame(top_frame)
        priorytet_frame.pack(anchor="w", pady=2)

        ttk.Label(priorytet_frame, text="Priorytet:").pack(side="left")

        self.priorytet_var = tk.StringVar(value=self.priorytet)
        combo_state = "readonly" if self.rola in ("TECHNIK", "ADMIN") else "disabled"
        self.priorytet_combo = ttk.Combobox(
            priorytet_frame,
            textvariable=self.priorytet_var,
            values=PRIORYTETY,
            state=combo_state,
            width=12,
        )
        self.priorytet_combo.pack(side="left", padx=5)

        self.btn_zapisz_priorytet = ttk.Button(
            priorytet_frame,
            text="Zapisz priorytet",
            command=self._zapisz_priorytet,
            state="normal" if self.rola in ("TECHNIK", "ADMIN") else "disabled",
        )
        self.btn_zapisz_priorytet.pack(side="left", padx=5)

        # --- BLOKADA PRIORYTETU WG UPRAWNIEŃ ---
        can_change_priority = False

        if self.rola == "ADMIN":
            can_change_priority = True
        elif self.rola == "TECHNIK":
            if self.czy_technik_przypisany and not self.czy_zamkniete:
                can_change_priority = True

        if not can_change_priority:
            self.priorytet_combo.config(state="disabled")
            self.btn_zapisz_priorytet.config(state="disabled")

        # przypisany technik
        przyp = pobierz_przypisanego_technika(self.zgl_id)
        self.lbl_przypisany = ttk.Label(
            top_frame,
            text=f"Przypisany technik: {przyp if przyp else 'brak'}",
        )
        self.lbl_przypisany.pack(anchor="w", pady=2)

        ctrl_frame = ttk.Frame(top_frame)
        ctrl_frame.pack(anchor="w", pady=4)

        self.btn_przypisz = None
        self.btn_zamknij = None

        if self.rola in ("TECHNIK", "ADMIN"):
            self.btn_przypisz = ttk.Button(
                ctrl_frame,
                text="Przypisz zgłoszenie",
                command=self._przypisz_do_mnie,
            )
            self.btn_przypisz.grid(row=0, column=3, padx=5)

        if self.rola in ("TECHNIK", "ADMIN"):
            self.btn_zamknij = ttk.Button(
                ctrl_frame,
                text="Zamknij zgłoszenie",
                command=self._zamknij_zgloszenie,
            )
            self.btn_zamknij.grid(row=0, column=4, padx=5)

        # przycisk usunięcia – TYLKO ADMIN
        self.btn_usun = ttk.Button(
            top_frame, text="Usuń zgłoszenie", command=self._usun_zgloszenie
        )
        if self.rola == "ADMIN":
            self.btn_usun.pack(pady=4)

        # dodatkowy przycisk dodawania zdjęć
        self.btn_dodaj_zdjecia = ttk.Button(
            top_frame,
            text="Dodaj zdjęcia",
            command=self._dodaj_zdjecia_pracownika,
        )

        if self.rola == "PRACOWNIK" and self.czy_pracownik_moze_edytowac:
            self.btn_dodaj_zdjecia.pack(pady=4)
        elif self.rola == "TECHNIK":
            self.btn_dodaj_zdjecia.pack(pady=4)
            if self.czy_technik_przypisany and not self.czy_zamkniete:
                self.btn_dodaj_zdjecia.config(state="normal")
            else:
                self.btn_dodaj_zdjecia.config(state="disabled")
        elif self.rola == "ADMIN" and not self.czy_zamkniete:
            self.btn_dodaj_zdjecia.pack(pady=4)

        # --- zdjęcia ---
        ramka_zdjec = ttk.LabelFrame(
            self, text="Zdjęcia (kliknij dwukrotnie, aby otworzyć)"
        )
        ramka_zdjec.pack(fill="both", expand=False, padx=10, pady=5)

        self.lista = tk.Listbox(
            ramka_zdjec,
            height=5,
            bg=input_bg,
            fg=colors["text"],
            selectbackground=colors["accent"],
            selectforeground="white",
            relief="flat",
            highlightthickness=1,
            highlightbackground=input_border,
        )
        self.lista.pack(fill="both", expand=True, padx=8, pady=6)
        for _, sciezka in zdj:
            self.lista.insert("end", sciezka)
        self.lista.bind("<Double-1>", self._otworz_zdjecie)

        # przycisk usunięcia zdjęcia – tylko dla ADMIN
        self.btn_usun_zdjecie = None
        if self.rola == "ADMIN":
            self.btn_usun_zdjecie = ttk.Button(
                ramka_zdjec,
                text="Usuń zaznaczone zdjęcie",
                command=self._usun_zdjecie,
            )
            self.btn_usun_zdjecie.pack(pady=(0, 6), anchor="e")

        # --- historia + komentarze ---
        bottom = ttk.Frame(self)
        bottom.pack(fill="both", expand=True, padx=10, pady=5)

        logs_frame = ttk.LabelFrame(bottom, text="Historia zgłoszenia")
        logs_frame.pack(fill="both", expand=True, side="top")

        kol = ("Czas", "Użytkownik", "Typ", "Szczegóły")
        self.logi_tree = ttk.Treeview(
            logs_frame,
            columns=kol,
            show="headings",
            height=7,
            style="DarkTreeview",  # ten sam styl, co lista zgłoszeń
        )
        for k in kol:
            self.logi_tree.heading(k, text=k)
        self.logi_tree.column("Czas", width=150)
        self.logi_tree.column("Użytkownik", width=120)
        self.logi_tree.column("Typ", width=130)
        self.logi_tree.column("Szczegóły", width=450)
        self.logi_tree.pack(fill="both", expand=True, padx=6, pady=4)

        kom_container = ttk.Frame(bottom)
        kom_container.pack(fill="both", expand=False, pady=5)

        # komentarz publiczny
        left = ttk.LabelFrame(
            kom_container,
            text="Komentarz dla pracownika (widoczny dla wszystkich)",
        )
        left.pack(side="left", fill="both", expand=True, padx=5)

        self.kom_public_text = tk.Text(
            left,
            height=4,
            bg=input_bg,
            fg=colors["text"],
            insertbackground=colors["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=input_border,
            highlightcolor=colors["accent"],
            wrap="word",
        )
        self.kom_public_text.pack(fill="both", expand=True, pady=2)

        self.btn_kom_pub = ttk.Button(
            left,
            text="Zapisz komentarz",
            command=self._dodaj_komentarz_publiczny,
        )
        self.btn_kom_pub.pack(anchor="e", pady=2)

        # komentarz wewnętrzny – tylko Technik/Admin
        self.kom_internal_text = None
        self.btn_kom_int = None
        if self.rola in ("TECHNIK", "ADMIN"):
            right = ttk.LabelFrame(
                kom_container,
                text="Notatka wewnętrzna (tylko Technik/Admin)",
            )
            right.pack(side="left", fill="both", expand=True, padx=5)

            self.kom_internal_text = tk.Text(
                right,
                height=4,
                bg=input_bg,
                fg=colors["text"],
                insertbackground=colors["text"],
                relief="flat",
                highlightthickness=1,
                highlightbackground=input_border,
                highlightcolor=colors["accent"],
                wrap="word",
            )
            self.kom_internal_text.pack(fill="both", expand=True, pady=2)

            self.btn_kom_int = ttk.Button(
                right,
                text="Zapisz notatkę",
                command=self._dodaj_komentarz_wewnetrzny,
            )
            self.btn_kom_int.pack(anchor="e", pady=2)

        # komentarz publiczny:
        if (
            self.rola == "PRACOWNIK"
            or (self.rola == "TECHNIK" and not self.czy_technik_przypisany)
        ):
            self.kom_public_text.config(state="disabled")
            self.btn_kom_pub.config(state="disabled")

        # notatka wewnętrzna:
        if (
            self.rola == "TECHNIK"
            and not self.czy_technik_przypisany
            and self.kom_internal_text is not None
        ):
            self.kom_internal_text.config(state="disabled")
            if self.btn_kom_int is not None:
                self.btn_kom_int.config(state="disabled")

        self._zaladuj_logi()
        self._zaladuj_pola_komentarzy()

        # jeśli zgłoszenie jest zamknięte – blokujemy wszystkich oprócz ADMINA
        if self.czy_zamkniete and self.rola != "ADMIN":
            self._zablokuj_wszystko_po_zamknieciu()

        # opis może edytować:
        can_edit_opis = False
        if self.rola == "PRACOWNIK" and self.czy_pracownik_moze_edytowac:
            can_edit_opis = True
        elif self.rola == "ADMIN" and not self.czy_zamkniete:
            can_edit_opis = True

        if not can_edit_opis:
            self.opis_text.config(state="disabled")
            self.btn_zapisz_opis.config(state="disabled")

        # pracownik nie może nic robić z przypisaniem / zamknięciem
        if self.rola == "PRACOWNIK":
            if self.btn_przypisz:
                self.btn_przypisz.configure(state="disabled")
            if self.btn_zamknij:
                self.btn_zamknij.configure(state="disabled")

    # ----- akcje -----
    def _zapisz_opis(self):
        """
        Zapis opisu zgłoszenia.

        Opis może zmieniać:
        - PRACOWNIK: tylko swoje zgłoszenie i tylko gdy jest OPEN/IN_PROGRESS,
        - ADMIN: do momentu zamknięcia zgłoszenia.
        """
        # nie pozwalamy edytować zamkniętego zgłoszenia (nawet jeśli ktoś ma aktywne pole)
        if self.czy_zamkniete:
            messagebox.showwarning(
                "Brak uprawnień",
                "Nie można edytować opisu zamkniętego zgłoszenia.", parent=self
            )
            return

        if self.rola == "PRACOWNIK":
            # pracownik – dodatkowo tylko swoje zgłoszenie i odpowiedni status
            if not self.czy_pracownik_moze_edytowac:
                messagebox.showwarning(
                    "Brak uprawnień",
                    "Nie możesz edytować opisu tego zgłoszenia.", parent=self
                )
                return

        elif self.rola == "ADMIN":
            # admin – może edytować (do momentu zamknięcia, sprawdzone wyżej)
            pass

        else:
            # TECHNIK i inne role
            messagebox.showwarning(
                "Brak uprawnień",
                "Tylko pracownik lub administrator może edytować opis zgłoszenia."
            )
            return

        nowy_opis = self.opis_text.get("1.0", "end").strip()


        # ----- zapis do bazy -----
        try:
            with polacz() as c:
                cur = c.cursor()
                cur.execute(
                    "UPDATE zgloszenia SET opis=?, zaktualizowano=? WHERE id=?",
                    (nowy_opis, teraz_iso(), self.zgl_id),
                )
                c.commit()
        except Exception as e:
            messagebox.showerror(
                "Błąd",
                f"Nie udało się zapisać opisu w bazie:\n{e}"
            )
            return

        # lokalna kopia danych też zaktualizowana
        if len(self.dane) > 2:
            self.dane[2] = nowy_opis

        # ----- log EDIT_DESCRIPTION -----
        try:
            dodaj_log(
                self.zgl_id,
                self.current_user_id,
                "EDIT_DESCRIPTION",
                "Zmieniono opis zgłoszenia.",
            )
        except Exception:
            # jeśli log się nie zapisze – nie blokujemy użytkownika
            pass

        # odśwież historia + listy w głównym oknie
        self._zaladuj_logi()
        if callable(self.on_change):
            self.on_change()

        messagebox.showinfo("OK", "Opis zgłoszenia zaktualizowano.", parent=self)
        # UWAGA: NIE zamykamy okna – użytkownik dalej je widzi

    def _zapisz_priorytet(self):
        nowy = (self.priorytet_var.get() or "NORMAL").strip()

        if nowy not in PRIORYTETY:
            messagebox.showwarning("Błąd", "Nieprawidłowy priorytet.", parent=self)
            return

        # nic się nie zmieniło
        if nowy == self.priorytet:
            return

        if not ustaw_priorytet_zgloszenia(self.zgl_id, nowy, self.current_user_id):
            messagebox.showerror(
                "Błąd",
                "Nie udało się zaktualizować priorytetu w bazie danych.",
            )
            return

        self.priorytet = nowy
        messagebox.showinfo("OK", "Priorytet został zaktualizowany.")

        # odśwież logi i listę zgłoszeń
        self._zaladuj_logi()
        if callable(self.on_change):
            self.on_change()

    def _dodaj_zdjecia_pracownika(self):
        """
        Dodawanie zdjęć do zgłoszenia.

        Może to zrobić:
        - PRACOWNIK: tylko swoje zgłoszenie w odpowiednim statusie
          (self.czy_pracownik_moze_edytowac),
        - TECHNIK: tylko po przejęciu zgłoszenia (self.czy_technik_przypisany)
          i gdy zgłoszenie nie jest zamknięte,
        - ADMIN: do momentu zamknięcia zgłoszenia.
        """
        # twarda blokada na zgłoszenie zamknięte
        if self.czy_zamkniete:
            messagebox.showwarning(
                "Brak uprawnień",
                "Nie można dodawać zdjęć do zamkniętego zgłoszenia.", parent=self
            )
            return

        # sprawdzamy uprawnienia zależnie od roli
        if self.rola == "PRACOWNIK":
            if not self.czy_pracownik_moze_edytowac:
                messagebox.showwarning(
                    "Brak uprawnień",
                    "Nie możesz dodawać zdjęć do tego zgłoszenia.",
                    parent=self,
                )
                return

        elif self.rola == "TECHNIK":
            if not getattr(self, "czy_technik_przypisany", False):
                messagebox.showwarning(
                    "Brak uprawnień",
                    "Najpierw przypisz zgłoszenie do siebie "
                    "(Przypisz zgłoszenie).",
                )
                return

        elif self.rola == "ADMIN":
            # admin – może dodawać zdjęcia, dopóki zgłoszenie nie jest zamknięte
            pass

        else:
            messagebox.showwarning(
                "Brak uprawnień",
                "Tylko pracownik, technik przypisany do zgłoszenia lub "
                "administrator mogą dodawać zdjęcia.",
            )
            return

        pliki = filedialog.askopenfilenames(
            title="Wybierz zdjęcia",
            filetypes=[("Obrazy", "*.jpg *.jpeg *.png *.bmp *.gif")],
        )
        if not pliki:
            return

        dodaj_zdjecia_do_zgloszenia(
            self.zgl_id,
            pliki,
            self.master_app.uzytkownik["id"],
        )
        # odśwież listę zdjęć
        self.lista.delete(0, "end")
        _, zdj = pobierz_zgloszenie(self.zgl_id)
        for _, sciezka in zdj:
            self.lista.insert("end", sciezka)
        messagebox.showinfo("OK", "Zdjęcia dodano do zgłoszenia.")
        if callable(self.on_change):
            self.on_change()
        self._zaladuj_logi()

    def _zamknij_zgloszenie(self):
        # tylko Technik albo Admin w ogóle widzą ten przycisk
        if self.rola not in ("TECHNIK", "ADMIN"):
            return

        # Technik musi mieć zgłoszenie przypisane do siebie
        if self.rola == "TECHNIK" and not self.czy_technik_przypisany:
            messagebox.showwarning(
                "Brak uprawnień",
                "Najpierw przypisz zgłoszenie do siebie (Przypisz zgłoszenie).",
            )
            return

        # jeżeli już zamknięte – nic nie rób
        if self.czy_zamkniete:
            messagebox.showinfo(
                "Zgłoszenie zamknięte",
                "To zgłoszenie jest już zamknięte.",
            )
            return

        if not messagebox.askyesno(
                "Zamknięcie zgłoszenia",
                "Czy na pewno chcesz zamknąć to zgłoszenie (status DONE)?",
                parent=self,
        ):
            return

        # >>> NOWE: zapis do bazy
        if not zamknij_zgloszenie(self.zgl_id, self.master_app.uzytkownik["id"]):
            messagebox.showerror(
                "Błąd",
                "Nie udało się zamknąć zgłoszenia w bazie danych.",
            )
            return
        # <<< KONIEC NOWEGO FRAGMENTU

        # aktualizacja lokalnego stanu
        self.status = "DONE"
        self.czy_zamkniete = True
        self.zamkniete_przez = self.master_app.uzytkownik["id"]

        # aktualizacja etykiety statusu
        if hasattr(self, "lbl_status"):
            self.lbl_status.config(text=f"Status: {self.status}")

        # po zamknięciu technik NIE jest już "aktywnym" opiekunem
        self.czy_technik_przypisany = False

        messagebox.showinfo("OK", "Zgłoszenie zostało zamknięte.", parent=self)
        self._zaladuj_logi()
        self._zaladuj_pola_komentarzy()

        # odśwież listę w oknie głównym
        if callable(self.on_change):
            self.on_change()

        # KLUCZ: każdy poza ADMINEM ma wszystko zablokowane
        if self.rola != "ADMIN":
            self._zablokuj_wszystko_po_zamknieciu()

    def _usun_zdjecie(self):
        # tylko ADMIN może usuwać pojedyncze zdjęcia
        if self.rola != "ADMIN":
            return

        sel = self.lista.curselection()
        if not sel:
            messagebox.showinfo(
                "Brak wyboru",
                "Najpierw zaznacz zdjęcie na liście.", parent=self
            )
            return

        sciezka = self.lista.get(sel[0])

        if not messagebox.askyesno(
            "Potwierdzenie",
            "Czy na pewno usunąć zaznaczone zdjęcie ze zgłoszenia?",
        ):
            return

        usun_zdjecie_ze_zgloszenia(
            self.zgl_id,
            sciezka,
            self.master_app.uzytkownik["id"],
        )

        # odśwież listę zdjęć
        self.lista.delete(0, "end")
        _, zdj = pobierz_zgloszenie(self.zgl_id)
        for _, s in zdj:
            self.lista.insert("end", s)

        if callable(self.on_change):
            self.on_change()
        self._zaladuj_logi()


    def _przypisz_do_mnie(self):
        if self.rola not in ("TECHNIK", "ADMIN"):
            return

        # NIE pozwalamy przypisywać zamkniętego zgłoszenia (oprócz admina)
        if self.czy_zamkniete and self.rola != "ADMIN":
            messagebox.showwarning(
                "Zgłoszenie zamknięte",
                "Nie można przypisać zamkniętego zgłoszenia."
            )
            return

        u = self.master_app.uzytkownik

        # ADMIN może przypisać do siebie nawet zamknięte zgłoszenie
        force_reopen = (self.rola == "ADMIN" and self.czy_zamkniete)

        if not przypisz_do_technika(self.zgl_id, u["id"], force_reopen=force_reopen):
            messagebox.showerror("Błąd", "Nie udało się przypisać zgłoszenia.")
            return

        # aktualizacja etykiet i stanu w oknie
        self.lbl_przypisany.config(text=f"Przypisany technik: {u['login']}")
        self.przypisany_technik_id = u["id"]
        self.czy_technik_przypisany = True

        # TECHNIK nie może edytować opisu pracownika – nawet po przejęciu
        if self.rola == "TECHNIK":
            self.opis_text.config(state="disabled")
            self.btn_zapisz_opis.config(state="disabled")

        # technik po przejęciu zgłoszenia może zmienić priorytet
        if hasattr(self, "priorytet_combo") and hasattr(self, "btn_zapisz_priorytet"):
            if not self.czy_zamkniete:     # tylko gdy zgłoszenie nie jest DONE
                self.priorytet_combo.config(state="readonly")
                self.btn_zapisz_priorytet.config(state="normal")


        # po przejęciu zgłoszenia TECHNIK może edytować opis
        #if self.rola == "TECHNIK" and not self.czy_zamkniete:
        #    self.czy_technik_moze_edytowac_opis = True
        #    self.czy_moze_edytowac_opis = True
        #    self.opis_text.config(state="normal")
        #    self.btn_zapisz_opis.config(state="normal")
        #   if self.btn_dodaj_zdjecia:
        #        self.btn_dodaj_zdjecia.config(state="normal")
        # TECHNIK nigdy nie może edytować opisu zgłoszenia
        if self.rola == "TECHNIK":
            can_edit_opis = False
            self.btn_zapisz_opis.state(["disabled"])

        # automatyczna zmiana statusu na IN_PROGRESS (W trakcie).
        # Dla ADMINA pozwalamy na ponowne otwarcie (DONE -> IN_PROGRESS).
        if self.status != "DONE" or (self.rola == "ADMIN" and self.czy_zamkniete):
            self.status = "IN_PROGRESS"
            self.czy_zamkniete = False  # już nie jest zamknięte
            self.zamkniete_przez = None  # czyścimy info o zamknięciu

            if hasattr(self, "lbl_status"):
                self.lbl_status.config(text=f"Status: {self.status}")

        # komentarze technika – włączamy, jeśli wcześniej były zablokowane
        if self.kom_public_text is not None and self.rola in ("TECHNIK", "ADMIN"):
            self.kom_public_text.config(state="normal")
        if self.btn_kom_pub is not None and self.rola in ("TECHNIK", "ADMIN"):
            self.btn_kom_pub.config(state="normal")
        if self.kom_internal_text is not None and self.rola in ("TECHNIK", "ADMIN"):
            self.kom_internal_text.config(state="normal")
        if self.btn_kom_int is not None and self.rola in ("TECHNIK", "ADMIN"):
            self.btn_kom_int.config(state="normal")

        # przycisk „Przypisz do mnie” po przypisaniu nie ma już sensu
        if self.btn_przypisz:
            self.btn_przypisz.configure(state="disabled")

        # log przypisania
        try:
            dodaj_log(
                self.zgl_id,
                u["id"],
                "ASSIGN",
                f"Przypisano do technika {u['login']}",
            )
        except Exception:
            pass

        # odśwież logi i listę w oknie głównym
        self._zaladuj_logi()
        if callable(self.on_change):
            self.on_change()

        messagebox.showinfo("OK", "Zgłoszenie przypisane.", parent=self)

    def _dodaj_komentarz_publiczny(self):
        # pracownik i tak ma przycisk wyłączony, ale dla pewności:
        if self.rola == "PRACOWNIK":
            return

        # zamknięte zgłoszenie – edytować może tylko admin
        if self.czy_zamkniete and self.rola != "ADMIN":
            messagebox.showwarning(
                "Zgłoszenie zamknięte",
                "Nie można dodawać komentarzy do zamkniętego zgłoszenia.", parent=self
            )
            return

        if self.rola == "PRACOWNIK":
            return
        tresc = self.kom_public_text.get("1.0", "end").strip()
        if not tresc:
            messagebox.showwarning("Błąd", "Komentarz nie może być pusty.")
            return
        try:
            dodaj_log(
                self.zgl_id,
                self.master_app.uzytkownik["id"],
                "COMMENT_PUBLIC",
                tresc,
            )
        except Exception:
            messagebox.showerror("Błąd", "Nie udało się zapisać komentarza.")
            return
        self._zaladuj_logi()
        self._zaladuj_pola_komentarzy()

    def _dodaj_komentarz_wewnetrzny(self):
        if self.rola == "TECHNIK" and not self.czy_technik_przypisany:
            messagebox.showwarning(
                "Brak uprawnień",
                "Najpierw przypisz zgłoszenie do siebie (Przypisz do mnie).", parent=self
            )
            return

        if self.rola not in ("TECHNIK", "ADMIN") or self.kom_internal_text is None:
            return

        if self.czy_zamkniete and self.rola != "ADMIN":
            messagebox.showwarning(
                "Zgłoszenie zamknięte",
                "Nie można dodawać notatek do zamkniętego zgłoszenia."
            )
            return

        if self.rola not in ("TECHNIK", "ADMIN") or self.kom_internal_text is None:
            return
        tresc = self.kom_internal_text.get("1.0", "end").strip()
        if not tresc:
            messagebox.showwarning("Błąd", "Notatka nie może być pusta.")
            return
        try:
            dodaj_log(
                self.zgl_id,
                self.master_app.uzytkownik["id"],
                "COMMENT_INTERNAL",
                tresc,
            )
        except Exception:
            messagebox.showerror("Błąd", "Nie udało się zapisać notatki.")
            return
        self._zaladuj_logi()
        self._zaladuj_pola_komentarzy()

    def _usun_zgloszenie(self):
        if self.rola != "ADMIN":
            return
        if messagebox.askyesno("Potwierdź", "Usunąć to zgłoszenie?"):
            usun_zgloszenie(self.zgl_id)
            try:
                dodaj_log(
                    self.zgl_id,
                    self.master_app.uzytkownik["id"],
                    "DELETE",
                    "Zgłoszenie usunięte przez administratora.",
                )
            except Exception:
                pass
            messagebox.showinfo("OK", "Zgłoszenie usunięto.")
            if callable(self.on_change):
                self.on_change()
            self.destroy()

    def _otworz_zdjecie(self, _evt=None):
        """
        Podgląd zdjęcia w osobnym oknie (bez użycia zewnętrznej aplikacji).
        """
        sel = self.lista.curselection()
        if not sel:
            return

        sciezka = self.lista.get(sel[0])

        if not os.path.exists(sciezka):
            messagebox.showerror("Błąd", f"Nie znaleziono pliku:\n{sciezka}")
            return

        # okno podglądu
        podglad = tk.Toplevel(self)
        podglad.title(os.path.basename(sciezka))

        try:
            # wczytanie obrazka – działa dla PNG/GIF (i kilku innych formatów)
            img = tk.PhotoImage(file=sciezka)
        except Exception as e:
            podglad.destroy()
            messagebox.showerror(
                "Błąd",
                f"Nie udało się wczytać obrazu:\n{e}", parent=self
            )
            return

        lbl = tk.Label(podglad, image=img)
        lbl.image = img  # trzymamy referencję, żeby obraz nie zniknął z pamięci
        lbl.pack(fill="both", expand=True)

        podglad.transient(self)
        podglad.grab_set()

    # ----- logi i komentarze -----
    def _zaladuj_logi(self):
        """Wczytuje logi zgłoszenia do tabeli."""
        # wyczyść aktualne wiersze
        for item in self.logi_tree.get_children():
            self.logi_tree.delete(item)

        # pobierz logi z bazy (używamy helpera z core)
        for czas, uzytkownik, typ, szczegoly in pobierz_logi(self.zgl_id, self.rola):
            self.logi_tree.insert("", "end", values=(czas, uzytkownik, typ, szczegoly))

    def _zaladuj_pola_komentarzy(self):
        """Ładuje ostatni komentarz publiczny i wewnętrzny do pól tekstowych."""

        def ostatni_komentarz(typ):
            with polacz() as c:
                cur = c.cursor()
                cur.execute(
                    """
                    SELECT szczegoly
                    FROM zgloszenia_logi
                    WHERE zgloszenie_id = ? AND typ = ?
                    ORDER BY czas DESC
                    LIMIT 1
                    """,
                    (self.zgl_id, typ),
                )
                row = cur.fetchone()
                return row[0] if row else ""

        # komentarz publiczny
        if self.kom_public_text is not None:
            tekst_pub = ostatni_komentarz("COMMENT_PUBLIC")
            self.kom_public_text.config(state="normal")
            self.kom_public_text.delete("1.0", "end")
            if tekst_pub:
                self.kom_public_text.insert("1.0", tekst_pub)

            # jeśli pracownik nie może pisać – zostawiamy jako tylko do odczytu
            if (
                self.rola == "PRACOWNIK"
                or (self.rola == "TECHNIK" and not self.czy_technik_przypisany)
            ):
                self.kom_public_text.config(state="disabled")
                self.btn_kom_pub.config(state="disabled")

        # notatka wewnętrzna (techniczna)
        if self.kom_internal_text is not None:
            tekst_int = ostatni_komentarz("COMMENT_INTERNAL")
            self.kom_internal_text.config(state="normal")
            self.kom_internal_text.delete("1.0", "end")
            if tekst_int:
                self.kom_internal_text.insert("1.0", tekst_int)

    # ----- blokada po zamknięciu zgłoszenia -----
    def _zablokuj_wszystko_po_zamknieciu(self):
        """Blokuje edycję pól i przycisków dla zamkniętego zgłoszenia."""
        # opis
        if hasattr(self, "opis_text"):
            self.opis_text.config(state="disabled")
        if hasattr(self, "btn_zapisz_opis"):
            self.btn_zapisz_opis.config(state="disabled")

        # komentarz publiczny
        if hasattr(self, "kom_public_text") and self.kom_public_text is not None:
            self.kom_public_text.config(state="disabled")
        if hasattr(self, "btn_kom_pub") and self.btn_kom_pub is not None:
            self.btn_kom_pub.config(state="disabled")

        # komentarz wewnętrzny
        if hasattr(self, "kom_internal_text") and self.kom_internal_text is not None:
            self.kom_internal_text.config(state="disabled")
        if hasattr(self, "btn_kom_int") and self.btn_kom_int is not None:
            self.btn_kom_int.config(state="disabled")

        # dodawanie zdjęć
        if hasattr(self, "btn_dodaj_zdjecia") and self.btn_dodaj_zdjecia is not None:
            self.btn_dodaj_zdjecia.config(state="disabled")

        # zmiana priorytetu
        if hasattr(self, "priorytet_combo"):
            self.priorytet_combo.config(state="disabled")
        if hasattr(self, "btn_zapisz_priorytet"):
            self.btn_zapisz_priorytet.config(state="disabled")

        # przypisanie / zamknięcie
        if hasattr(self, "btn_przypisz") and self.btn_przypisz is not None:
            self.btn_przypisz.config(state="disabled")
        if hasattr(self, "btn_zamknij") and self.btn_zamknij is not None:
            self.btn_zamknij.config(state="disabled")
