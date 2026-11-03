"""`LocaControl.exe`: one executable, a few verbs (P1-E).

- `abrir` (default): on the main computer, starts the server in the background if it is not
  running and opens the browser; on a station, opens the store's address;
- `servir`: runs the server (app.server); in the windowed executable its output goes to
  `<data>/logs/servidor.log`;
- `servico`: the same server hosted by the Windows service "LocaControl" (SEC-P1E-01), which runs
  under its own identity `NT SERVICE\\LocaControl`; only the service manager starts this verb;
- `conectar --servidor <endereço> --codigo <código>`: "Conectar à loja" (app.network.connect);
- `desconectar`: removes the trust a station installed (uninstall);
- `nova-autoridade --confirmar`: replaces the store's CA after a change of network (SEC-P1E-04);
- `parar`: controlled stop of the server of this data folder (update and uninstall, REL-P1E-02):
  asks it to finish what is in progress and waits; forces only after the wait, and never with
  `--sem-forcar`.
"""

import argparse
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

from app.core.config import data_root

DEFAULT_PORT = 8000
LOG_LIMIT = 10 * 1024 * 1024
EXIT_CONNECT_FAILED = 2
EXIT_NOT_STARTED = 6
# `parar`: the server did not finish within the wait and was ended by force (the next start
# checks the database), or, with --sem-forcar, it is still running and nothing was forced.
EXIT_FORCED = 7
EXIT_STILL_RUNNING = 9
EXIT_NO_PERMISSION = 13
STOP_WAIT = 180
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
    from app.network.connect import station_url

    url = station_url()
    if url:
        if browser:
            webbrowser.open(url)
        return 0
    if not health(port):
        from app import winservice

        if winservice.installed():
            winservice.start()  # the service runs as its own identity, never as this user
        else:
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


def log_folders():
    """`<data>/logs`, then this user's own folder: since SEC-P1E-01 a Windows user without
    administrator rights cannot write in the data folder."""
    yield data_root() / "logs"
    if local := os.environ.get("LOCALAPPDATA"):
        yield Path(local) / "LocaControl" / "logs"


def redirect_output(name: str = "servidor.log"):
    """The windowed executable has no console: keep its messages in a log file. Never fails: with
    no writable folder the messages are dropped, as they would be without a console."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    for folder in log_folders():
        try:
            folder.mkdir(parents=True, exist_ok=True)
            log = folder / name
            if log.exists() and log.stat().st_size > LOG_LIMIT:
                os.replace(log, log.with_suffix(".log.1"))
            stream = open(log, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
        except OSError:
            continue
        sys.stdout = sys.stderr = stream
        return


def server_running(root: Path) -> bool:
    """True while a server holds the lock of this data folder (more reliable than the PID file,
    whose number may by now belong to another program)."""
    from app.server import AlreadyRunning, acquire_lock

    try:
        handle = acquire_lock(root)
    except AlreadyRunning:
        return True
    handle.close()
    return False


def stop(wait: float = STOP_WAIT, force: bool = True) -> int:
    """Controlled stop (REL-P1E-02): ask, wait for backups/requests to finish, force only last."""
    from app import winservice
    from app.server import PID_FILE, STOP_FILE

    root = data_root()
    try:
        if not server_running(root):
            return 0
        if winservice.running():
            winservice.stop()  # the service manager's STOP: same controlled path
        else:
            (root / STOP_FILE).write_text("parar", encoding="ascii")
    except PermissionError:
        print(
            "Sem permissão para encerrar o LocaControl (use uma conta de administrador).",
            file=sys.stderr,
        )
        return EXIT_NO_PERMISSION
    deadline = time.monotonic() + wait
    while server_running(root):
        if time.monotonic() > deadline:
            break
        time.sleep(0.5)
    else:
        return 0
    if not force:
        print(
            f"O LocaControl não terminou em {wait:.0f} s (backup ou gravação em andamento?). "
            "Nada foi forçado; tente de novo em alguns minutos.",
            file=sys.stderr,
        )
        return EXIT_STILL_RUNNING
    try:
        pid = int((root / PID_FILE).read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return EXIT_STILL_RUNNING
    print(
        f"O LocaControl não terminou em {wait:.0f} s e foi encerrado à força; o banco será "
        "verificado no próximo início.",
        file=sys.stderr,
    )
    kill(pid)
    deadline = time.monotonic() + 30
    while server_running(root) and time.monotonic() < deadline:
        time.sleep(0.2)
    # The PID file stays: the next start sees an unclean end and runs integrity_check.
    return EXIT_FORCED


def new_authority() -> int:
    """SEC-P1E-04: the store moved to another network (or the CA must be replaced). Stops the
    server in a controlled way, moves the CA aside (never deletes it) and starts again; the next
    start creates a new CA for the networks of now. Every station must connect again."""
    from app import winservice
    from app.core.config import Settings
    from app.network.stations import registry_for
    from app.network.tls import TLS_FOLDER, LocalAuthority

    folder = registry_for(Settings()).path.parent / TLS_FOLDER
    was_service = winservice.running()
    code = stop(force=False)
    if code:
        return code
    try:
        moved = LocalAuthority(folder).retire()
    except PermissionError:
        print("Sem permissão (use uma conta de administrador).", file=sys.stderr)
        return EXIT_NO_PERMISSION
    print(
        f"Autoridade anterior guardada em {moved}. " if moved else "Não havia autoridade. ",
        "Uma nova será criada no próximo início do servidor. Em cada estação, execute de novo "
        'o instalador com "Conectar à loja" e um código novo.',
    )
    if was_service:
        winservice.start()
    return 0


def kill(pid: int):
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return
    import signal

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    verb = argv.pop(0) if argv and not argv[0].startswith("-") else "abrir"
    redirect_output("servidor.log" if verb in ("servir", "servico") else COMMANDS_LOG)
    if verb == "servir":
        from app import server

        return server.main(argv)
    if verb == "servico":
        from app import server, winservice

        return winservice.host(lambda stop_event, started: server.main(argv, stop_event, started))
    parser = argparse.ArgumentParser(prog="LocaControl", description="LocaControl")
    parser.add_argument("--porta", type=int, default=DEFAULT_PORT)
    if verb == "conectar":
        parser.add_argument("--servidor", required=True)
        parser.add_argument("--codigo", required=True)
        parser.add_argument("--sem-navegador", action="store_true")
        parser.add_argument("--resultado", type=Path, help="arquivo lido pelo instalador")
        args = parser.parse_args(argv)
        from app.network.connect import DEFAULT_PORT as HTTPS_PORT
        from app.network.connect import ConnectError, connect, write_result

        port = args.porta if args.porta != DEFAULT_PORT else HTTPS_PORT
        try:
            record = connect(args.servidor, args.codigo, port, open_browser=not args.sem_navegador)
        except Exception as error:  # noqa: BLE001 — every failure must reach the installer
            message = str(error) if isinstance(error, ConnectError) else f"Erro inesperado: {error}"
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} conectar: {message}", file=sys.stderr)
            if args.resultado:
                write_result(args.resultado, False, message)
            return EXIT_CONNECT_FAILED
        # Only the certificate is settled here; the station is paired in the browser (UX-P1E-03).
        message = (
            f"Certificado da loja {record['url']} conferido pelo código e instalado "
            f"(autoridade {record['ca_fingerprint'][:23]}…). Falta concluir o pareamento no "
            "navegador."
        )
        print(message)
        if args.resultado:
            write_result(args.resultado, True, message, record["pairing_url"])
        return 0
    if verb == "desconectar":
        from app.network.connect import disconnect

        disconnect()
        return 0
    if verb == "parar":
        parser.add_argument("--espera", type=float, default=STOP_WAIT)
        parser.add_argument("--sem-forcar", action="store_true")
        args = parser.parse_args(argv)
        return stop(args.espera, force=not args.sem_forcar)
    if verb == "nova-autoridade":
        parser.add_argument("--confirmar", action="store_true")
        args = parser.parse_args(argv)
        if not args.confirmar:
            print(
                "Cria uma nova autoridade certificadora da loja (quando a loja muda de rede). "
                "Todas as estações precisarão conectar de novo. Repita com --confirmar.",
                file=sys.stderr,
            )
            return 64
        return new_authority()
    if verb == "abrir":
        parser.add_argument("--sem-navegador", action="store_true")
        args = parser.parse_args(argv)
        return open_app(args.porta, browser=not args.sem_navegador)
    print(f"Comando desconhecido: {verb}", file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main())
