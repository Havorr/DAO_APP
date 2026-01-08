from core import inicjalizuj_baze
from ui.login import OknoLogowania
from ui.main_window import Aplikacja


def main():
    inicjalizuj_baze()

    chce_wylogowac = True
    while chce_wylogowac:
        # 1. okno logowania
        okno_log = OknoLogowania()
        okno_log.mainloop()

        # jeśli użytkownik się nie zalogował / zamknął okno – kończymy
        if not getattr(okno_log, "zalogowany", None):
            return

        # 2. główne okno po zalogowaniu
        app = Aplikacja(okno_log.zalogowany)
        app.mainloop()

        # jeśli w Aplikacja ustawisz self.chce_wylogowac = True przy wylogowaniu,
        # to pętla wykona się ponownie (wróci do logowania)
        chce_wylogowac = bool(getattr(app, "chce_wylogowac", False))


if __name__ == "__main__":
    main()
