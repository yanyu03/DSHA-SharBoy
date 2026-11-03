"""KDI-P03 isolated positive and negative resource-admission regression."""

from concurrent.futures import ThreadPoolExecutor
import threading
import unittest

from scripts.kdi_resource_admission import ResourceAdmission, ResourceAdmissionError, Decision


class ResourceAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.gate = ResourceAdmission({"cpu": 2, "network": 1})

    def test_assess_is_non_reserving(self):
        self.assertEqual(self.gate.assess({"cpu": 2}), Decision("OK", "ready"))
        self.assertEqual(self.gate.usage(), {"cpu": 0, "network": 0})

    def test_acquire_reserves_and_release_restores(self):
        decision, token = self.gate.acquire({"cpu": 2, "network": 1})
        self.assertEqual(decision.state, "OK")
        self.assertIsNotNone(token)
        self.assertEqual(self.gate.usage(), {"cpu": 2, "network": 1})
        self.assertTrue(self.gate.release(token))
        self.assertEqual(self.gate.usage(), {"cpu": 0, "network": 0})

    def test_busy_is_later_and_no_token(self):
        _, token = self.gate.acquire({"network": 1})
        decision, rejected = self.gate.acquire({"network": 1})
        self.assertEqual(decision, Decision("LATER", "busy"))
        self.assertIsNone(rejected)
        self.assertTrue(self.gate.release(token))
        self.assertEqual(self.gate.acquire({"network": 1})[0].state, "OK")

    def test_demand_exceeding_capacity_is_never(self):
        self.assertEqual(self.gate.acquire({"cpu": 3}), (Decision("NEVER", "exceeds_capacity"), None))

    def test_unknown_resource_is_never(self):
        self.assertEqual(self.gate.acquire({"gpu": 1}), (Decision("NEVER", "unknown_resource"), None))

    def test_permanent_mismatch_precedes_busy(self):
        self.gate.acquire({"network": 1})
        self.assertEqual(self.gate.assess({"network": 1, "cpu": 3}), Decision("NEVER", "exceeds_capacity"))
        self.assertEqual(self.gate.assess({"network": 1, "gpu": 1}), Decision("NEVER", "unknown_resource"))

    def test_atomic_multi_resource_no_partial_reservation(self):
        self.gate.acquire({"network": 1})
        decision, token = self.gate.acquire({"cpu": 2, "network": 1})
        self.assertEqual(decision.state, "LATER")
        self.assertIsNone(token)
        self.assertEqual(self.gate.usage(), {"cpu": 0, "network": 1})

    def test_releasing_foreign_or_repeated_token_fails_closed(self):
        _, token = self.gate.acquire({"cpu": 1})
        other = ResourceAdmission({"cpu": 1})
        self.assertFalse(other.release(token))
        self.assertFalse(self.gate.release(object()))
        self.assertFalse(self.gate.release([]))
        self.assertTrue(self.gate.release(token))
        self.assertFalse(self.gate.release(token))
        self.assertEqual(self.gate.usage()["cpu"], 0)

    def test_bounded_lease_registry(self):
        gate = ResourceAdmission({"cpu": 3}, max_leases=1)
        _, token = gate.acquire({"cpu": 1})
        self.assertEqual(gate.acquire({"cpu": 1}), (Decision("LATER", "lease_limit"), None))
        self.assertTrue(gate.release(token))
        self.assertEqual(gate.acquire({"cpu": 1})[0].state, "OK")

    def test_capacity_and_max_lease_validation(self):
        for config in ({}, {"cpu": 0}, {"cpu": True}, {"CPU": 1}, {"cpu\n": 1},
                       {"cpu": 1025}, {"cpu": -1}, {"x": 1.0}, {"x": "1"},
                       {str(i): 1 for i in range(17)}, None):
            with self.subTest(config=config), self.assertRaises(ResourceAdmissionError):
                ResourceAdmission(config)
        for n in (True, 0, -1, 1025, 1.5):
            with self.subTest(n=n), self.assertRaises(ResourceAdmissionError):
                ResourceAdmission({"cpu": 1}, max_leases=n)

    def test_demand_validation(self):
        for demand in ({}, {"cpu": 0}, {"cpu": True}, {"cpu": -1},
                       {"cpu": 1025}, {"CPU": 1}, {"bad\nname": 1},
                       {"cpu": 1.0}, None, []):
            with self.subTest(demand=demand), self.assertRaises(ResourceAdmissionError):
                self.gate.acquire(demand)
        self.assertEqual(self.gate.usage(), {"cpu": 0, "network": 0})

    def test_assess_then_acquire_is_not_guaranteed(self):
        self.assertEqual(self.gate.assess({"network": 1}).state, "OK")
        self.gate.acquire({"network": 1})
        self.assertEqual(self.gate.acquire({"network": 1})[0].state, "LATER")

    def test_independent_resources_do_not_block_each_other(self):
        self.gate.acquire({"network": 1})
        self.assertEqual(self.gate.acquire({"cpu": 2})[0].state, "OK")

    def test_simultaneous_contenders_cannot_oversubscribe(self):
        for _ in range(30):
            gate = ResourceAdmission({"cpu": 1})
            barrier = threading.Barrier(2)
            def contender():
                barrier.wait(timeout=5)
                return gate.acquire({"cpu": 1})
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(contender)
                second = pool.submit(contender)
                results = [first.result(timeout=5), second.result(timeout=5)]
            self.assertEqual(sorted(x[0].state for x in results), ["LATER", "OK"])
            self.assertEqual(gate.usage()["cpu"], 1)
            for _, token in results:
                if token is not None:
                    self.assertTrue(gate.release(token))
            self.assertEqual(gate.usage()["cpu"], 0)

    def test_parallel_release_and_acquire_stay_bounded(self):
        gate = ResourceAdmission({"cpu": 1})
        _, token = gate.acquire({"cpu": 1})
        barrier = threading.Barrier(2)
        def release():
            barrier.wait(timeout=5)
            return gate.release(token)
        def acquire():
            barrier.wait(timeout=5)
            return gate.acquire({"cpu": 1})
        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(release)
            f2 = pool.submit(acquire)
            self.assertTrue(f1.result(timeout=5))
            decision, new_token = f2.result(timeout=5)
        self.assertIn(decision.state, ("OK", "LATER"))
        self.assertIn(gate.usage()["cpu"], (0, 1))
        if new_token is not None:
            self.assertTrue(gate.release(new_token))
        self.assertEqual(gate.usage()["cpu"], 0)


if __name__ == "__main__":
    unittest.main()
