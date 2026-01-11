# Okno resetu hasła
import tkinter as tk
from tkinter import ttk, messagebox
import random
import string
import os

from ui.theme import get_colors, apply_entry_style
from core import (
    pobierz_uzytkownika_po_loginie,
    ustaw_token_reset,
    ustaw_haslo,
    teraz_iso,
    polacz,
    KATALOG,
)

# -------------------- Helper: centrowanie okien --------------------
def wycentruj_okno(okno):
    okno.update_idletasks()

    # pobierz aktualny lub wymagany rozmiar okna
    w = okno.winfo_width()
    h = okno.winfo_height()
    if w <= 1 or h <= 1:
        w = okno.winfo_reqwidth()
        h = okno.winfo_reqheight()

    # rozdzielczość ekranu
    sw = okno.winfo_screenwidth()
    sh = okno.winfo_screenheight()

    # pozycja na środku ekranu
    x = (sw - w) // 2
    y = (sh - h) // 2

    okno.geometry(f"+{x}+{y}")


# -------------------- Okno resetu hasła --------------------
class ResetHasloOkno(tk.Toplevel):
    """
    1) Login + kod odzyskiwania.
    2) Po poprawnym wpisaniu generujemy kod, tworzymy folder RESET_<kod>
       i pokazujemy drugi krok (kod z folderu + nowe hasło).
    """

    def __init__(self, master):
        super().__init__(master)

        colors = get_colors()

        self.title("Reset hasła")
        self.geometry("520x280")
        self.minsize(520, 280)
        self.configure(bg=colors["bg"])
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        try:
            self.iconbitmap("app_icon.ico")
        except Exception:
            pass

        # stan
        self.wygenerowany_kod = None
        self.login_sprawdzony = None
        self.folder_kodu = None
        self.krok2_utworzony = False

        # kolory pól
        self._entry_bg = colors["input_bg"]
        self._entry_fg = colors["text"]

        # ---------- KARTA ----------
        outer = tk.Frame(self, bg=colors["bg"])
        outer.pack(expand=True, fill="both", padx=20, pady=16)

        border = tk.Frame(outer, bg=colors["border"])
        border.pack(expand=True, fill="both")

        card = tk.Frame(border, bg=colors["card_bg"])
        card.pack(expand=True, fill="both", padx=1, pady=1)

        # nagłówek
        header = tk.Frame(card, bg=colors["card_bg"])
        header.pack(fill="x", pady=(6, 0), padx=12)

        icon_lbl = tk.Label(
            header,
            text="🔑",
            bg=colors["card_bg"],
            fg=colors["text"],
            font=("Segoe UI Emoji", 16),
        )
        icon_lbl.pack(side="left")

        title_lbl = tk.Label(
            header,
            text="Reset hasła",
            bg=colors["card_bg"],
            fg=colors["text"],
            font=("Segoe UI Semibold", 13),
        )
        title_lbl.pack(side="left", padx=(8, 0))

        subtitle_lbl = tk.Label(
            card,
            text="Podaj login i token odzyskiwania, aby wygenerować kod resetu.",
            bg=colors["card_bg"],
            fg=colors["muted"],
            font=("Segoe UI", 9),
        )
        subtitle_lbl.pack(fill="x", anchor="w", padx=12, pady=(2, 6))

        line = tk.Frame(card, bg=colors["border"], height=1)
        line.pack(fill="x", padx=12, pady=(0, 10))

        # ---------- FORMULARZ KROK 1 ----------
        form = tk.Frame(card, bg=colors["card_bg"])
        form.pack(fill="x", padx=12, pady=(0, 4))

        form.columnconfigure(0, weight=0)
        form.columnconfigure(1, weight=1)
        self._form = form  # do kroku 2

        # login
        self.login_entry = self._make_labeled_entry(
            parent=form, row=0, label_text="Login"
        )

        # kod odzyskiwania
        self.kod_odz_entry = self._make_labeled_entry(
            parent=form, row=1, label_text="Kod odzyskiwania"
        )

        # przycisk „Sprawdź i generuj kod”
        btn_row = tk.Frame(form, bg=colors["card_bg"])
        btn_row.grid(row=2, column=0, columnspan=2, sticky="e", pady=(6, 2))

        self.btn_generuj = tk.Button(
            btn_row,
            text="Sprawdź i generuj kod",
            font=("Segoe UI Semibold", 9),
            fg="white",
            bg=colors["accent"],
            activeforeground="white",
            activebackground=colors["accent_hover"],
            bd=0,
            padx=18,
            pady=5,
            cursor="hand2",
            command=self._wygeneruj_kod,
        )
        self.btn_generuj.pack(side="right")

        # opis pomocniczy na dole
        help_lbl = tk.Label(
            card,
            text=(
                "Po wygenerowaniu kodu w katalogu programu pojawi się folder "
                "RESET_<KOD>. Odczytaj kod z nazwy folderu, wpisz go w kolejnym "
                "kroku i ustaw nowe hasło."
            ),
            bg=colors["card_bg"],
            fg=colors["muted"],
            font=("Segoe UI", 8),
            justify="left",
            wraplength=440,
        )
        help_lbl.pack(fill="x", padx=12, pady=(8, 6))

        self.login_entry.focus()
        wycentruj_okno(self)

    # ---------- helper z ramką + highlight ----------
    def _make_labeled_entry(self, parent, row, label_text, show=None):
        colors = get_colors()

        lbl = tk.Label(
            parent,
            text=label_text,
            bg=colors["card_bg"],
            fg=colors["text"],
            font=("Segoe UI", 9),
        )
        lbl.grid(row=row, column=0, sticky="e", padx=(0, 8), pady=(0, 4))

        wrapper = tk.Frame(parent, bg=colors["border"], bd=1, relief="solid")
        wrapper.grid(row=row, column=1, sticky="we", pady=(0, 6))
        wrapper.grid_propagate(False)

        inner = tk.Frame(wrapper, bg=colors["card_bg"], padx=1, pady=1)
        inner.pack(fill="both", expand=True)

        entry = tk.Entry(
            inner,
            font=("Segoe UI", 10),
            bg=self._entry_bg,
            fg=self._entry_fg,
            insertbackground=self._entry_fg,
            relief="flat",
            bd=0,
            show=show,
        )
        entry.pack(fill="x", padx=6, pady=4)

        # highlight ramki
        def on_focus_in(event, w=wrapper):
            w.config(bg=colors["accent"])

        def on_focus_out(event, w=wrapper):
            w.config(bg=colors["border"])

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

        return entry

    # ---------- LOGIKA krok 1 ----------
    def _wygeneruj_kod(self):
        login = self.login_entry.get().strip()
        kod_odz = self.kod_odz_entry.get().strip()

        if not login or not kod_odz:
            messagebox.showwarning("Błąd", "Podaj login i kod odzyskiwania.")
            return

        u = pobierz_uzytkownika_po_loginie(login)
        # u: (id, login, haslo, rola, kod_odzyskiwania, budynek_id)
        if not u or not u[4] or u[4] != kod_odz:
            messagebox.showerror("Błąd", "Niepoprawny login lub kod odzyskiwania.")
            return

        self.login_sprawdzony = login
        self.wygenerowany_kod = "".join(
            random.choices(string.ascii_letters + string.digits + "_-", k=10)
        )

        self.folder_kodu = os.path.join(KATALOG, f"RESET_{self.wygenerowany_kod}")
        os.makedirs(self.folder_kodu, exist_ok=True)

        messagebox.showinfo(
            "Kod wygenerowany",
            "W katalogu programu utworzono folder z kodem weryfikacyjnym.\n"
            "Odczytaj kod z nazwy folderu (RESET_...) i wpisz go poniżej,\n"
            "a następnie ustaw nowe hasło."
        )

        if not self.krok2_utworzony:
            self._zbuduj_krok2()
        else:
            self.kod_folderu_entry.delete(0, "end")
            self.nowe_haslo_entry.delete(0, "end")
            self.nowe_haslo2_entry.delete(0, "end")

    # ---------- UI i logika krok 2 ----------
    def _zbuduj_krok2(self):
        colors = get_colors()

        row = 3  # po login/kodzie/przycisku

        self.kod_folderu_entry = self._make_labeled_entry(
            parent=self._form,
            row=row,
            label_text="Kod z folderu RESET_:",
        )

        row += 1
        self.nowe_haslo_entry = self._make_labeled_entry(
            parent=self._form,
            row=row,
            label_text="Nowe hasło:",
            show="*",
        )

        row += 1
        self.nowe_haslo2_entry = self._make_labeled_entry(
            parent=self._form,
            row=row,
            label_text="Powtórz hasło:",
            show="*",
        )

        row += 1
        btn_row = tk.Frame(self._form, bg=colors["card_bg"])
        btn_row.grid(row=row, column=0, columnspan=2, sticky="e", pady=(8, 4))

        self.btn_zmien_haslo = tk.Button(
            btn_row,
            text="Ustaw nowe hasło",
            font=("Segoe UI Semibold", 9),
            fg="white",
            bg=colors["accent"],
            activeforeground="white",
            activebackground=colors["accent_hover"],
            bd=0,
            padx=18,
            pady=6,
            cursor="hand2",
            command=self._zmien_haslo,
        )
        self.btn_zmien_haslo.pack(side="right")

        self.krok2_utworzony = True

        # dopasuj rozmiar i wycentruj po dodaniu kroku 2
        self.update_idletasks()
        w = max(520, self.winfo_width())
        h = self.winfo_reqheight()
        self.geometry(f"{w}x{h}")
        self.minsize(w, h)
        wycentruj_okno(self)

    def _zmien_haslo(self):
        if not self.wygenerowany_kod or not self.login_sprawdzony:
            messagebox.showerror("Błąd", "Najpierw wygeneruj kod weryfikacyjny.")
            return

        kod_z_folderu = self.kod_folderu_entry.get().strip()
        nowe_haslo = self.nowe_haslo_entry.get().strip()
        nowe_haslo2 = self.nowe_haslo2_entry.get().strip()

        if not kod_z_folderu or not nowe_haslo or not nowe_haslo2:
            messagebox.showwarning("Błąd", "Wypełnij wszystkie pola.")
            return

        if kod_z_folderu != self.wygenerowany_kod:
            messagebox.showerror("Błąd", "Niepoprawny kod z folderu.")
            return

        if nowe_haslo != nowe_haslo2:
            messagebox.showerror("Błąd", "Hasła nie są takie same.")
            return

        if len(nowe_haslo) < 6:
            messagebox.showwarning("Błąd", "Hasło powinno mieć co najmniej 6 znaków.")
            return

        if ustaw_haslo(self.login_sprawdzony, nowe_haslo):
            if self.folder_kodu and os.path.isdir(self.folder_kodu):
                try:
                    os.rmdir(self.folder_kodu)
                except OSError:
                    pass

            messagebox.showinfo(
                "Sukces",
                "Hasło zostało zmienione.\nZamknij to okno i zaloguj się nowym hasłem."
            )
            self.destroy()
        else:
            messagebox.showerror("Błąd", "Nie udało się zmienić hasła.")

# -------------------- Okno logowania --------------------
class OknoLogowania(tk.Tk):
    def __init__(self):
        super().__init__()

        apply_entry_style(self)
        colors = get_colors()

        # --- okno ---
        self.title("System Zgłoszeń Usterek – logowanie")
        self.geometry("520x300")
        self.minsize(520, 300)
        self.configure(bg=colors["bg"])
        self.resizable(False, False)

        try:
            self.iconbitmap("app_icon.ico")
        except Exception:
            pass

        self.zalogowany = None

        # REFERENCJA DO OKNA RESETU HASŁA
        self.reset_okno = None

        # ---------- RAMKA + KARTA ----------
        outer = tk.Frame(self, bg=colors["bg"])
        outer.pack(expand=True, fill="both", padx=20, pady=16)

        border = tk.Frame(outer, bg=colors["border"])
        border.pack(expand=True, fill="both")

        card = tk.Frame(border, bg=colors["card_bg"])
        card.pack(expand=True, fill="both", padx=1, pady=1)

        # ---------- NAGŁÓWEK ----------
        header = tk.Frame(card, bg=colors["card_bg"])
        header.pack(fill="x", pady=(6, 0), padx=12)

        icon_lbl = tk.Label(
            header,
            text="🛠️",
            bg=colors["card_bg"],
            fg=colors["text"],
            font=("Segoe UI Emoji", 16),
        )
        icon_lbl.pack(side="left")

        title_lbl = tk.Label(
            header,
            text="System zgłoszeń usterek",
            bg=colors["card_bg"],
            fg=colors["text"],
            font=("Segoe UI Semibold", 13),
        )
        title_lbl.pack(side="left", padx=(8, 0))

        subtitle_lbl = tk.Label(
            card,
            text="Zaloguj się używając konta z systemu.",
            bg=colors["card_bg"],
            fg=colors["muted"],
            font=("Segoe UI", 9),
        )
        subtitle_lbl.pack(fill="x", anchor="w", padx=12, pady=(2, 6))

        line = tk.Frame(card, bg=colors["border"], height=1)
        line.pack(fill="x", padx=12, pady=(0, 10))

        # ---------- FORMULARZ ----------
        form = tk.Frame(card, bg=colors["card_bg"])
        form.pack(fill="x", padx=12, pady=(0, 4))

        form.columnconfigure(0, weight=0)
        form.columnconfigure(1, weight=1)

        entry_bg = colors["input_bg"]
        entry_fg = colors["text"]
        self._entry_bg = entry_bg
        self._entry_fg = entry_fg

        # login
        self.login_entry = self._create_labeled_entry(
            form, row=0, label_text="Login"
        )

        # hasło
        self.haslo_entry = self._create_labeled_entry(
            form, row=1, label_text="Hasło", show="*"
        )

        # checkbox blisko pola hasła
        self._show_password_var = tk.BooleanVar(value=False)
        cb_show = tk.Checkbutton(
            form,
            text="Pokaż hasło",
            variable=self._show_password_var,
            command=self._toggle_password,
            bg=colors["card_bg"],
            fg=colors["text"],
            activebackground=colors["card_bg"],
            activeforeground=colors["text"],
            selectcolor=colors["card_bg"],
            font=("Segoe UI", 9),
        )
        cb_show.grid(row=2, column=1, sticky="w", pady=(2, 8))

        # ---------- PRZYCISKI ----------
        btn_row = tk.Frame(card, bg=colors["card_bg"])
        btn_row.pack(fill="x", padx=12, pady=(4, 4))

        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=0)
        btn_row.columnconfigure(2, weight=0)

        btn_reset = tk.Button(
            btn_row,
            text="Reset hasła",
            font=("Segoe UI", 9),
            fg=colors["text"],
            bg=colors["card_bg"],
            activeforeground=colors["text"],
            activebackground=colors["border"],
            bd=1,
            relief="solid",
            padx=14,
            pady=4,
            cursor="hand2",
            command=self._otworz_reset,
        )
        btn_reset.grid(row=0, column=1, sticky="e", padx=(0, 8))

        self.btn_login = tk.Button(
            btn_row,
            text="Zaloguj",
            font=("Segoe UI Semibold", 10),
            fg="white",
            bg=colors["accent"],
            activeforeground="white",
            activebackground=colors["accent_hover"],
            bd=0,
            padx=20,
            pady=6,
            cursor="hand2",
            command=self._zaloguj,
        )
        self.btn_login.grid(row=0, column=2, sticky="e")

        self.btn_login.bind("<Enter>", self._on_login_hover)
        self.btn_login.bind("<Leave>", self._on_login_leave)

        # ---------- TEKST POMOCNICZY ----------
        help_lbl = tk.Label(
            card,
            text="Problemy z logowaniem? Skontaktuj się z administratorem systemu.",
            bg=colors["card_bg"],
            fg=colors["muted"],
            font=("Segoe UI", 8),
            wraplength=440,
            justify="left",
        )
        help_lbl.pack(fill="x", padx=12, pady=(6, 6))

        # focus + Enter
        self.login_entry.focus()
        self.bind("<Return>", lambda e: self._zaloguj())
        wycentruj_okno(self)

    # ---------- helper do pól z ramką + highlight ----------
    def _create_labeled_entry(self, parent, row, label_text, show=None):
        colors = get_colors()

        lbl = tk.Label(
            parent,
            text=label_text,
            bg=colors["card_bg"],
            fg=colors["text"],
            font=("Segoe UI", 9),
        )
        lbl.grid(row=row, column=0, sticky="e", padx=(0, 8), pady=(0, 4))

        wrapper = tk.Frame(parent, bg=colors["border"], bd=1, relief="solid")
        wrapper.grid(row=row, column=1, sticky="we", pady=(0, 6))
        wrapper.grid_propagate(False)

        inner = tk.Frame(wrapper, bg=colors["card_bg"], bd=0, padx=1, pady=1)
        inner.pack(fill="both", expand=True)

        entry = tk.Entry(
            inner,
            font=("Segoe UI", 10),
            bg=self._entry_bg,
            fg=self._entry_fg,
            insertbackground=self._entry_fg,
            relief="flat",
            bd=0,
            show=show,
        )
        entry.pack(fill="x", padx=6, pady=4)

        # highlight ramki przy fokusie
        def on_focus_in(event, w=wrapper):
            w.config(bg=colors["accent"])

        def on_focus_out(event, w=wrapper):
            w.config(bg=colors["border"])

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

        return entry

    # ---------- pomocnicze ----------
    def _toggle_password(self):
        self.haslo_entry.config(show="" if self._show_password_var.get() else "*")

    def _on_login_hover(self, _evt=None):
        colors = get_colors()
        self.btn_login.config(bg=colors["accent_hover"])

    def _on_login_leave(self, _evt=None):
        colors = get_colors()
        self.btn_login.config(bg=colors["accent"])

    # ---------- LOGIKA bez zmian ----------
    def _zaloguj(self):
        login = self.login_entry.get().strip()
        haslo = self.haslo_entry.get().strip()

        if not login or not haslo:
            messagebox.showwarning("Błąd", "Podaj login i hasło.")
            return

        u = pobierz_uzytkownika_po_loginie(login)
        if u and u[2] == haslo:
            self.zalogowany = {
                "id": u[0],
                "login": u[1],
                "rola": u[3],
                "budynek_id": u[5],
            }
            try:
                with polacz() as c:
                    cur = c.cursor()
                    cur.execute(
                        "UPDATE uzytkownicy SET ostatnie_logowanie=? WHERE id=?",
                        (teraz_iso(), u[0]),
                    )
                    c.commit()
            except Exception:
                pass
            self.destroy()
        else:
            messagebox.showerror("Błąd", "Niepoprawny login lub hasło.")

    def _otworz_reset(self):
        # jeśli okno już jest otwarte – tylko je pokaż / ustaw na wierzchu
        if self.reset_okno is not None and self.reset_okno.winfo_exists():
            self.reset_okno.lift()
            self.reset_okno.focus_force()
            return

        # tworzymy nowe okno resetu hasła
        self.reset_okno = ResetHasloOkno(self)

        # gdy okno zostanie zniszczone (X lub destroy),
        # wyczyść referencję żeby można było otworzyć ponownie
        self.reset_okno.bind(
            "<Destroy>",
            lambda e: setattr(self, "reset_okno", None)
        )

