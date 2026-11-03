"""`LocaControl.exe`: one executable, a few verbs (P1-E).

- `abrir` (default): on the main computer, starts the server in the background if it is not
  running and opens the browser; on a station, opens the store's address;
- `servir`: runs the server (app.server); in the windowed executable its output goes to
  `<data>/logs/servidor.log`;
- `conectar --servidor <endereço> --codigo <código>`: "Conectar à loja" (app.network.connect);
- `desconectar`: removes the trust a station installed (uninstall);
- `parar`: stops the server of this data folder (update and uninstall).
"""

import argparse
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser

from app.core.config import data_root

DEFAULT_PORT = 8000
LOG_LIMIT = 10 * 1024 * 1024
EXIT_CONNECT_FAILED = 2
EXIT_NOT_STARTED = 6
COMMANDS_LOG = "comandos.log"  # conectar/desconectar/parar/abrir in the windowed executable


def health(port: int, timeout: float = 2) -> bool:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}/health", timeout=timeout) as response:
            return response.status == 200
    except OSError:
        return False


def server_command(port: int) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "servir", "--port", str(port)]
    return [sys.executable, "-m", "app.launcher", "servir", "--port", str(port)]


def spawn(command: list[str]):
    """The server outlives this process and has no window of its own."""
    options = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        options["creationflags"] = (
            subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_NO_WINDOW
        )
    else:
        options["start_new_session"] = True
    return subprocess.Popen(command, **options)


def open_app(port: int, browser: bool = True, wait: float = 90) -> int:
    from app.network.connect import read_station

    station = read_station()
    if station.get("url"):
        if browser:
            webbrowser.open(station["url"])
        return 0
    if not health(port):
        spawn(server_command(port))
        deadline = time.monotonic() + wait
        while not health(port):
            if time.monotonic() > deadline:
                print(
                    "O LocaControl não iniciou. Veja o arquivo "
                    f"{data_root() / 'logs' / 'servidor.log'}.",
                    file=sys.stderr,
                )
                return EXIT_NOT_STARTED
            time.sleep(0.5)
    if browser:
        webbrowser.open(f"http://127.0.0.1:{port}/")
    return 0


def redirect_output(name: str = "servidor.log"):
    """The windowed executable has no console: keep its messages in `<data>/logs/<name>`."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    folder = data_root() / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / name
    if log.exists() and log.stat().st_size > LOG_LIMIT:
        os.replace(log, log.with_suffix(".log.1"))
    stream = open(log, "a", encoding="utf-8", buffering=1)  # noqa: SIM115 — lives with the process
    sys.stdout = sys.stderr = stream


def stop(wait: float = 30) -> int:
    from app.server import PID_FILE

    pid_file = data_root() / PID_FILE
    try:
        pid = int(pid_file.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return 0  # nothing running from this data folder
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    else:
        import signal

        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + wait
    while pid_alive(pid) and time.monotonic() < deadline:
        time.sleep(0.2)
    pid_file.unlink(missing_ok=True)
    return 0


def pid_alive(pid: int) -> bool:
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return str(pid) in result.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    verb = argv.pop(0) if argv and not argv[0].startswith("-") else "abrir"
    redirect_output("servidor.log" if verb == "servir" else COMMANDS_LOG)
    if verb == "servir":
        from app import server

        return server.main(argv)
    parser = argparse.ArgumentParser(prog="LocaControl", description="LocaControl")
    parser.add_argument("--porta", type=int, default=DEFAULT_PORT)
    if verb == "conectar":
        parser.add_argument("--servidor", required=True)
        parser.add_argument("--codigo", required=True)
        parser.add_argument("--sem-navegador", action="store_true")
        args = parser.parse_args(argv)
        from app.network.connect import DEFAULT_PORT as HTTPS_PORT
        from app.network.connect import ConnectError, connect

        port = args.porta if args.porta != DEFAULT_PORT else HTTPS_PORT
        try:
            record = connect(args.servidor, args.codigo, port, open_browser=not args.sem_navegador)
        except ConnectError as error:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} conectar: {error}", file=sys.stderr)
            return EXIT_CONNECT_FAILED
        print(f"Conectado à loja {record['url']} (autoridade {record['ca_fingerprint'][:23]}…).")
        return 0
    if verb == "desconectar":
        from app.network.connect import disconnect

        disconnect()
        return 0
    if verb == "parar":
        return stop()
    if verb == "abrir":
        parser.add_argument("--sem-navegador", action="store_true")
        args = parser.parse_args(argv)
        return open_app(args.porta, browser=not args.sem_navegador)
    print(f"Comando desconhecido: {verb}", file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main())
