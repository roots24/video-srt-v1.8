import socket
import threading
import time
import pytest

import config
from conftest import make_logic


def test_retry_riesce_dopo_fallimenti():
    logic = make_logic()
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("boom")
        return 42

    result = logic._retry_with_backoff(flaky, max_retries=3, initial_delay=0)
    assert result == 42
    assert attempts["n"] == 3


def test_retry_rilancia_dopo_esaurimento():
    logic = make_logic()

    def always_fails():
        raise ValueError("sempre ko")

    with pytest.raises(ValueError, match="sempre ko"):
        logic._retry_with_backoff(always_fails, max_retries=2, initial_delay=0)


def test_retry_nessun_sleep_dopo_ultimo_tentativo():
    """Con retry=2, dopo il fallimento finale non deve dormire (nessun delay)."""
    logic = make_logic()

    def always_fails():
        raise ValueError("ko")

    start = time.monotonic()
    with pytest.raises(ValueError):
        logic._retry_with_backoff(always_fails, max_retries=1, initial_delay=5)
    assert time.monotonic() - start < 1


def test_retry_timeout():
    logic = make_logic()

    def slow():
        time.sleep(5)
        return "troppo tardi"

    with pytest.raises(Exception, match="Timeout dopo 0.1s"):
        logic._retry_with_backoff(slow, timeout=0.1, max_retries=1, initial_delay=0)


def test_execute_with_retry_default_timeout():
    """execute_with_retry senza timeout usa config.API_TIMEOUT."""
    logic = make_logic()
    assert logic.execute_with_retry(lambda: 7) == 7


def test_retry_timeout_rilascia_chiamante_presto():
    """Fix 4.2: con un'operazione appesa oltre il timeout, il chiamante deve
    essere rilasciato entro ~timeout (non bloccato finché l'op non finisce)."""
    logic = make_logic()

    def slow():
        time.sleep(3)
        return "troppo tardi"

    start = time.monotonic()
    with pytest.raises(Exception, match="Timeout"):
        logic._retry_with_backoff(slow, timeout=0.2, max_retries=1, initial_delay=0)
    assert time.monotonic() - start < 1.5


def test_retry_timeout_thread_non_e_zombie():
    """Fix 4.2: il task dell'executor non resta appeso in eterno: completa
    l'operazione (qui: sleep finito) e termina. Senza i fix (socket default
    timeout / edge-tts timeout) un socket appeso lo manterrebbe vivo."""
    logic = make_logic()
    done = threading.Event()

    def slow():
        time.sleep(0.3)
        done.set()
        return "tardi"

    with pytest.raises(Exception, match="Timeout"):
        logic._retry_with_backoff(slow, timeout=0.1, max_retries=1, initial_delay=0)
    # Il thread del task completa l'operazione e non resta in zombie
    assert done.wait(timeout=3.0)


def test_config_socket_default_timeout_impostato():
    """Fix 4.2: importando config, il timeout di default a livello socket è
    API_TIMEOUT → requests/urllib senza timeout esplicito (es. deep_translator)
    non possono restare appesi per sempre."""
    assert socket.getdefaulttimeout() == config.API_TIMEOUT