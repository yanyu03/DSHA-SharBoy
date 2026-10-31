"""KDI-P02 deterministic cancellation tests; no shell, network, or tool calls."""

from concurrent.futures import Future, ThreadPoolExecutor
import threading
import unittest

from scripts.kdi_preparation_gate import AdmissionError, PreparationGate


class PreparationGateTests(unittest.TestCase):
    def setUp(self):
        self.gate = PreparationGate(max_tasks=4)

    def test_pending_to_ready_to_claimed_exactly_once(self):
        f = Future()
        self.gate.register("one", f)
        self.assertEqual(self.gate.pump(), 0)
        f.set_result({"safe": True})
        self.assertEqual(self.gate.pump(), 1)
        self.assertEqual(self.gate.pump(), 0)
        self.assertEqual(self.gate.claim_ready(), ("one", {"safe": True}))
        self.assertIsNone(self.gate.claim_ready())
        self.assertEqual(self.gate.status("one"), "CLAIMED")

    def test_cancel_before_preparation_begins(self):
        f = Future()
        self.gate.register("one", f)
        self.assertTrue(self.gate.cancel("one"))
        self.assertTrue(f.cancelled())
        self.assertEqual(self.gate.pump(), 0)
        self.assertIsNone(self.gate.claim_ready())
        self.assertEqual(self.gate.status("one"), "CANCELLED")

    def test_cancel_during_running_preparation_cannot_readmit(self):
        f = Future()
        self.assertTrue(f.set_running_or_notify_cancel())
        self.gate.register("one", f)
        self.assertTrue(self.gate.cancel("one"))
        self.assertFalse(f.cancelled())
        f.set_result("late completion")
        self.assertEqual(self.gate.pump(), 0)
        self.assertIsNone(self.gate.claim_ready())
        self.assertEqual(self.gate.status("one"), "CANCELLED")

    def test_cancel_completed_future_before_pump(self):
        f = Future()
        self.gate.register("one", f)
        f.set_result("already finished")
        self.assertTrue(self.gate.cancel("one"))
        self.assertEqual(self.gate.pump(), 0)
        self.assertIsNone(self.gate.claim_ready())

    def test_cancel_after_ready_before_claim(self):
        f = Future()
        self.gate.register("one", f)
        f.set_result("valid")
        self.assertEqual(self.gate.pump(), 1)
        self.assertTrue(self.gate.cancel("one"))
        self.assertIsNone(self.gate.claim_ready())
        self.assertEqual(self.gate.status("one"), "CANCELLED")

    def test_cancel_after_claim_is_explicitly_too_late(self):
        f = Future()
        self.gate.register("one", f)
        f.set_result("valid")
        self.gate.pump()
        self.assertEqual(self.gate.claim_ready(), ("one", "valid"))
        self.assertFalse(self.gate.cancel("one"))

    def test_repeat_cancel_is_idempotent(self):
        f = Future()
        self.gate.register("one", f)
        self.assertTrue(self.gate.cancel("one"))
        self.assertTrue(self.gate.cancel("one"))
        self.assertEqual(self.gate.status("one"), "CANCELLED")

    def test_cancel_unknown_returns_false(self):
        self.assertFalse(self.gate.cancel("nonexistent"))
        self.assertIsNone(self.gate.status("nonexistent"))

    def test_failed_future_never_admitted(self):
        f = Future()
        self.gate.register("bad", f)
        f.set_exception(RuntimeError("preflight failed"))
        self.assertEqual(self.gate.pump(), 0)
        self.assertEqual(self.gate.status("bad"), "FAILED")
        self.assertFalse(self.gate.cancel("bad"))
        self.assertIsNone(self.gate.claim_ready())

    def test_cancel_one_task_does_not_affect_other(self):
        first, second = Future(), Future()
        self.gate.register("a", first)
        self.gate.register("b", second)
        self.assertTrue(self.gate.cancel("a"))
        second.set_result("good")
        self.assertEqual(self.gate.pump(), 1)
        self.assertEqual(self.gate.claim_ready(), ("b", "good"))
        self.assertIsNone(self.gate.claim_ready())

    def test_cannot_reuse_cancelled_task_id(self):
        self.gate.register("a", Future())
        self.gate.cancel("a")
        with self.assertRaises(AdmissionError):
            self.gate.register("a", Future())

    def test_fails_closed_on_capacity_exhaustion(self):
        for idx in range(4):
            self.gate.register(str(idx), Future())
        with self.assertRaises(AdmissionError):
            self.gate.register("overflow", Future())

    def test_invalid_task_ids_and_future(self):
        for task_id in ("", "bad\nname", "x" * 129, None):
            with self.subTest(task_id=task_id), self.assertRaises(AdmissionError):
                self.gate.register(task_id, Future())
        with self.assertRaises(AdmissionError):
            self.gate.register("a", "not a future")
        for size in (True, 0, 1025):
            with self.subTest(size=size), self.assertRaises(AdmissionError):
                PreparationGate(max_tasks=size)

    def test_racing_cancel_and_claim_is_linearizable(self):
        for _ in range(30):
            gate = PreparationGate()
            future = Future()
            gate.register("race", future)
            future.set_result("prepared")
            self.assertEqual(gate.pump(), 1)
            barrier = threading.Barrier(2)
            observed = {}

            def cancel():
                barrier.wait(timeout=5)
                observed["cancelled"] = gate.cancel("race")

            thread = threading.Thread(target=cancel)
            thread.start()
            try:
                barrier.wait(timeout=5)
                claimed = gate.claim_ready()
            finally:
                thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            if observed["cancelled"]:
                self.assertIsNone(claimed)
                self.assertEqual(gate.status("race"), "CANCELLED")
            else:
                self.assertEqual(claimed, ("race", "prepared"))
                self.assertEqual(gate.status("race"), "CLAIMED")

    def test_real_worker_completion_after_cancel_is_discarded(self):
        started = threading.Event()
        finish = threading.Event()

        def prepare():
            started.set()
            if not finish.wait(5):
                raise RuntimeError("test synchronisation timed out")
            return "worker result"

        with ThreadPoolExecutor(max_workers=1) as pool:
            f = pool.submit(prepare)
            self.assertTrue(started.wait(5), "worker did not start")
            try:
                self.gate.register("running", f)
                self.assertTrue(self.gate.cancel("running"))
            finally:
                finish.set()
            self.assertEqual(f.result(timeout=5), "worker result")
            self.assertEqual(self.gate.pump(), 0)
            self.assertIsNone(self.gate.claim_ready())


if __name__ == "__main__":
    unittest.main()
