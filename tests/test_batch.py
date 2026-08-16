from logic import BatchProcessor, ProcessingGuard


class FakeEngine:
    """Simula logic_engine.process: esito configurabile per item."""
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def process(self, *args, **kwargs):
        ok = self.results[self.calls]
        self.calls += 1
        return (ok, "ok" if ok else "errore simulato")


def test_process_all_conteggia_successi_e_progress():
    logs, progress = [], []
    bp = BatchProcessor(logs.append, progress_callback=lambda v, t: progress.append((v, t)))
    for i in range(3):
        bp.add_to_queue(f"b{i}.srt", "", f"b{i}.mp3", "en", "it", "male",
                        False, 1.5, 0.4, 1.0, "audio", False)

    success, total = bp.process_all(FakeEngine([True, False, True]))

    assert (success, total) == (2, 3)
    assert bp.is_running is False
    assert progress == [(1 / 3, "Batch 1/3"), (2 / 3, "Batch 2/3"), (3 / 3, "Batch 3/3")]
    summary = [m for m in logs if 'Batch completato' in m]
    assert summary and '2/3 successi' in summary[0]


def test_process_all_coda_vuota():
    bp = BatchProcessor(lambda m: None)
    success, total = bp.process_all(FakeEngine([]))
    assert (success, total) == (0, 0)


def test_process_all_resiliente_a_eccezioni():
    class ExplodingEngine:
        def process(self, *a, **k):
            raise RuntimeError("crash")

    logs = []
    bp = BatchProcessor(logs.append)
    bp.add_to_queue("b.srt", "", "b.mp3", "en", "it", "male", False, 1.5, 0.4, 1.0, "audio", False)

    success, total = bp.process_all(ExplodingEngine())
    assert (success, total) == (0, 1)
    assert any('errore' in m.lower() for m in logs)


def test_add_to_queue_e_clear():
    bp = BatchProcessor(lambda m: None)
    bp.add_to_queue("a.srt", "v.mp4", "out.mp4", "en", "it", "male", False, 1.5, 0.4, 1.0, "video", True)
    assert len(bp.queue) == 1
    item = bp.queue[0]
    assert item['srt'] == "a.srt" and item['mode'] == "video" and item['embed_srt'] is True
    bp.clear_queue()
    assert bp.queue == []


# ----------------------------------------------------------------------
# Fix 3.1: guardia condivisa batch <-> produzione singola
# (la GUI usa questo guard in start_batch/start_production)
# ----------------------------------------------------------------------

def test_guard_rifiuta_avvio_concorrente():
    """Una pipeline attiva (batch O singola) deve rifiutare l'altra."""
    guard = ProcessingGuard()
    assert guard.active is False

    # Avvia la produzione singola
    assert guard.try_begin() is True
    assert guard.active is True

    # Il batch concorrente viene rifiutato
    assert guard.try_begin() is False

    # Al termine la guardia si libera e si può riavviare
    guard.end()
    assert guard.active is False
    assert guard.try_begin() is True
    guard.end()


def test_guard_simula_batch_poi_singola():
    """Simula il flusso batch → singola: la seconda è rifiutata finché la prima corre.
    Riflette l'uso reale della GUI: end() è chiamato SOLO da chi ha acquisito."""
    guard = ProcessingGuard()

    # Batch in corso (ha acquisito la guardia)
    assert guard.try_begin() is True
    # Produzione singola tentata durante il batch → rifiuto, NON chiama end()
    assert guard.try_begin() is False
    assert guard.active is True  # il batch resta in corso
    # Il batch termina: è l'unico che libera la guardia
    guard.end()

    # Dopo il batch, la singola può partire
    assert guard.try_begin() is True
    guard.end()
    assert guard.active is False