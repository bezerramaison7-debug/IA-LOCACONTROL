"""Windows service "LocaControl" (SEC-P1E-01, REL-P1E-02).

On the main computer the server runs as a Windows service under its own identity, the virtual
account `NT SERVICE\\LocaControl`. The data folder (database, .env, station list, certificate
keys) is then readable and writable only by that identity, SYSTEM and administrators — not by the
other Windows users of the computer, who keep using the system through the browser.

- `host(run)`: what `LocaControl.exe servico` does when the service manager starts it. `run` is
  called as `run(stop_event, on_started)`; a STOP, SHUTDOWN or PRESHUTDOWN request sets
  `stop_event` (controlled shutdown: requests in progress, backups and restores finish first), and
  the status stays STOP_PENDING with a moving checkpoint until `run` returns.
- `state()`, `installed()`, `running()`, `start()`, `stop()`: queries and requests to the service
  manager. The installer lets interactive users start the service (so the desktop shortcut can
  bring it up) but only administrators can stop it.

Only the standard library (ctypes); outside Windows every query answers "not installed".
"""

import ctypes
import os
import sys
import threading
import traceback

SERVICE_NAME = "LocaControl"

STOPPED, START_PENDING, STOP_PENDING, RUNNING = 1, 2, 3, 4
_OWN_PROCESS = 0x10
_ACCEPT_STOP, _ACCEPT_SHUTDOWN, _ACCEPT_PRESHUTDOWN = 0x1, 0x4, 0x100
_CONTROL_STOP, _CONTROL_INTERROGATE, _CONTROL_SHUTDOWN, _CONTROL_PRESHUTDOWN = 1, 4, 5, 0xF
_SC_MANAGER_CONNECT = 0x1
_QUERY_STATUS, _START, _STOP = 0x4, 0x10, 0x20
_ERROR_ALREADY_RUNNING = 1056
_ERROR_NOT_FROM_SCM = 1063
_ERROR_SERVICE_SPECIFIC = 1066
_ERROR_CALL_NOT_IMPLEMENTED = 120
_PULSE = 5  # seconds between checkpoints while starting or stopping
_WAIT_HINT = 30_000  # milliseconds the service manager waits for the next checkpoint

DWORD = ctypes.c_uint32


class _Status(ctypes.Structure):
    _fields_ = [
        ("dwServiceType", DWORD),
        ("dwCurrentState", DWORD),
        ("dwControlsAccepted", DWORD),
        ("dwWin32ExitCode", DWORD),
        ("dwServiceSpecificExitCode", DWORD),
        ("dwCheckPoint", DWORD),
        ("dwWaitHint", DWORD),
    ]


def _advapi():
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi.OpenSCManagerW.restype = ctypes.c_void_p
    advapi.OpenSCManagerW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, DWORD]
    advapi.OpenServiceW.restype = ctypes.c_void_p
    advapi.OpenServiceW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, DWORD]
    advapi.CloseServiceHandle.argtypes = [ctypes.c_void_p]
    advapi.QueryServiceStatus.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Status)]
    advapi.StartServiceW.argtypes = [ctypes.c_void_p, DWORD, ctypes.c_void_p]
    advapi.ControlService.argtypes = [ctypes.c_void_p, DWORD, ctypes.POINTER(_Status)]
    advapi.SetServiceStatus.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Status)]
    return advapi


def _with_service(access: int, action):
    """Runs `action(advapi, handle)` on the service opened with `access`; None if impossible."""
    if os.name != "nt":
        return None
    advapi = _advapi()
    manager = advapi.OpenSCManagerW(None, None, _SC_MANAGER_CONNECT)
    if not manager:
        return None
    try:
        handle = advapi.OpenServiceW(manager, SERVICE_NAME, access)
        if not handle:
            return None
        try:
            return action(advapi, handle)
        finally:
            advapi.CloseServiceHandle(handle)
    finally:
        advapi.CloseServiceHandle(manager)


def state() -> int | None:
    """The service's current state, or None when it is not installed (or not Windows)."""

    def query(advapi, handle):
        status = _Status()
        return (
            status.dwCurrentState
            if advapi.QueryServiceStatus(handle, ctypes.byref(status))
            else None
        )

    return _with_service(_QUERY_STATUS, query)


def installed() -> bool:
    return state() is not None


def running() -> bool:
    return state() in (START_PENDING, RUNNING)


def start() -> bool:
    def request(advapi, handle):
        if advapi.StartServiceW(handle, 0, None):
            return True
        return ctypes.get_last_error() == _ERROR_ALREADY_RUNNING

    return bool(_with_service(_START, request))


def stop() -> bool:
    """Asks the service to stop (controlled shutdown); returns without waiting."""

    def request(advapi, handle):
        status = _Status()
        return bool(advapi.ControlService(handle, _CONTROL_STOP, ctypes.byref(status)))

    return bool(_with_service(_STOP, request))


def host(run) -> int:
    """Hosts `run(stop_event, on_started)` as the service; returns its exit code."""
    if os.name != "nt":
        print("O verbo 'servico' existe só no Windows; use 'servir'.", file=sys.stderr)
        return 64
    advapi = _advapi()
    handler_type = ctypes.WINFUNCTYPE(DWORD, DWORD, DWORD, ctypes.c_void_p, ctypes.c_void_p)
    main_type = ctypes.WINFUNCTYPE(None, DWORD, ctypes.POINTER(ctypes.c_wchar_p))

    class Entry(ctypes.Structure):
        _fields_ = [("name", ctypes.c_wchar_p), ("main", main_type)]

    advapi.RegisterServiceCtrlHandlerExW.restype = ctypes.c_void_p
    advapi.RegisterServiceCtrlHandlerExW.argtypes = [
        ctypes.c_wchar_p,
        handler_type,
        ctypes.c_void_p,
    ]
    advapi.StartServiceCtrlDispatcherW.argtypes = [ctypes.POINTER(Entry)]

    stop_event, finished = threading.Event(), threading.Event()
    guard = threading.Lock()
    status = _Status(_OWN_PROCESS, START_PENDING, 0, 0, 0, 0, _WAIT_HINT)
    context = {"handle": None, "code": 0}

    def report(new_state: int, exit_code: int = 0):
        with guard:
            pending = new_state in (START_PENDING, STOP_PENDING)
            status.dwCheckPoint = status.dwCheckPoint + 1 if pending else 0
            status.dwCurrentState = new_state
            status.dwWaitHint = _WAIT_HINT if pending else 0
            status.dwControlsAccepted = (
                _ACCEPT_STOP | _ACCEPT_SHUTDOWN | _ACCEPT_PRESHUTDOWN
                if new_state in (START_PENDING, RUNNING)
                else 0
            )
            if exit_code:
                status.dwWin32ExitCode = _ERROR_SERVICE_SPECIFIC
                status.dwServiceSpecificExitCode = exit_code
            if context["handle"]:
                advapi.SetServiceStatus(context["handle"], ctypes.byref(status))

    def pulse():
        # Long migrations, backups or restores: keep telling the manager we are progressing.
        while not finished.wait(_PULSE):
            if status.dwCurrentState in (START_PENDING, STOP_PENDING):
                report(status.dwCurrentState)

    @handler_type
    def handler(control, _event, _data, _context):
        if control in (_CONTROL_STOP, _CONTROL_SHUTDOWN, _CONTROL_PRESHUTDOWN):
            print("Serviço: encerramento pedido pelo Windows.", flush=True)
            report(STOP_PENDING)
            stop_event.set()
            return 0
        if control == _CONTROL_INTERROGATE:
            return 0
        return _ERROR_CALL_NOT_IMPLEMENTED

    def started():
        if not stop_event.is_set():
            report(RUNNING)

    @main_type
    def service_main(_argc, _argv):
        context["handle"] = advapi.RegisterServiceCtrlHandlerExW(SERVICE_NAME, handler, None)
        report(START_PENDING)
        threading.Thread(target=pulse, name="locacontrol-service-pulse", daemon=True).start()
        try:
            code = run(stop_event, started) or 0
        except BaseException:  # noqa: BLE001 — reported to the service manager, then logged
            traceback.print_exc()
            code = 1
        context["code"] = code
        finished.set()
        report(STOPPED, code)

    table = (Entry * 2)(Entry(SERVICE_NAME, service_main), Entry())
    if not advapi.StartServiceCtrlDispatcherW(table):
        if ctypes.get_last_error() == _ERROR_NOT_FROM_SCM:
            print(
                "O verbo 'servico' é iniciado só pelo Windows (serviço LocaControl); "
                "para rodar o servidor diretamente, use 'servir'.",
                file=sys.stderr,
            )
        return 64
    return context["code"]
