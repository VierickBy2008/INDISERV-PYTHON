"""IndiServ Analytica — Lanzador mínimo hacia núcleo compilado en C nativo."""

from ui.app_core import AppIndiServ, run_app

__all__ = ["AppIndiServ", "run_app"]

if __name__ == "__main__":
    run_app()
