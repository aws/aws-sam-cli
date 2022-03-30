from unittest import TestCase
from unittest.mock import MagicMock, call, patch
from samcli.lib.utils.lock_distributor import LockChain, LockDistributor, LockDistributorType


class TestLockChain(TestCase):
    def test_aquire_order(self):
        locks = {"A": MagicMock(), "B": MagicMock(), "C": MagicMock()}
        call_mock = MagicMock()
        call_mock.a = locks["A"]
        call_mock.b = locks["B"]
        call_mock.c = locks["C"]
        lock_chain = LockChain(locks)
        lock_chain.acquire()
        call_mock.assert_has_calls([call.a.acquire(), call.b.acquire(), call.c.acquire()])

    def test_aquire_order_shuffled(self):
        locks = {"A": MagicMock(), "C": MagicMock(), "B": MagicMock()}
        call_mock = MagicMock()
        call_mock.a = locks["A"]
        call_mock.b = locks["B"]
        call_mock.c = locks["C"]
        lock_chain = LockChain(locks)
        lock_chain.acquire()
        call_mock.assert_has_calls([call.a.acquire(), call.b.acquire(), call.c.acquire()])

    def test_release_order(self):
        locks = {"A": MagicMock(), "B": MagicMock(), "C": MagicMock()}
        call_mock = MagicMock()
        call_mock.a = locks["A"]
        call_mock.b = locks["B"]
        call_mock.c = locks["C"]
        lock_chain = LockChain(locks)
        lock_chain.release()
        call_mock.assert_has_calls([call.a.release(), call.b.release(), call.c.release()])

    def test_release_order_shuffled(self):
        locks = {"A": MagicMock(), "C": MagicMock(), "B": MagicMock()}
        call_mock = MagicMock()
        call_mock.a = locks["A"]
        call_mock.b = locks["B"]
        call_mock.c = locks["C"]
        lock_chain = LockChain(locks)
        lock_chain.release()
        call_mock.assert_has_calls([call.a.release(), call.b.release(), call.c.release()])

    def test_with(self):
        locks = {"A": MagicMock(), "C": MagicMock(), "B": MagicMock()}
        call_mock = MagicMock()
        call_mock.a = locks["A"]
        call_mock.b = locks["B"]
        call_mock.c = locks["C"]
        with LockChain(locks) as _:
            call_mock.assert_has_calls([call.a.acquire(), call.b.acquire(), call.c.acquire()])
        call_mock.assert_has_calls(
            [call.a.acquire(), call.b.acquire(), call.c.acquire(), call.a.release(), call.b.release(), call.c.release()]
        )


class TestLockDistributor(TestCase):
    @patch("samcli.lib.utils.lock_distributor.threading.Lock")
    @patch("samcli.lib.utils.lock_distributor.multiprocessing.Lock")
    def test_thread_get_locks(self, process_lock_mock, thread_lock_mock):
        locks = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
        thread_lock_mock.side_effect = locks
        distributor = LockDistributor(LockDistributorType.THREAD, None)
        keys = ["A", "B", "C"]
        result = distributor.get_locks(keys)

        self.assertEqual(result["A"], locks[1])
        self.assertEqual(result["B"], locks[2])
        self.assertEqual(result["C"], locks[3])
        self.assertEqual(distributor.get_locks(keys)["A"], locks[1])

    @patch("samcli.lib.utils.lock_distributor.threading.Lock")
    @patch("samcli.lib.utils.lock_distributor.multiprocessing.Lock")
    def test_process_get_locks(self, process_lock_mock, thread_lock_mock):
        locks = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
        process_lock_mock.side_effect = locks
        distributor = LockDistributor(LockDistributorType.PROCESS, None)
        keys = ["A", "B", "C"]
        result = distributor.get_locks(keys)

        self.assertEqual(result["A"], locks[1])
        self.assertEqual(result["B"], locks[2])
        self.assertEqual(result["C"], locks[3])
        self.assertEqual(distributor.get_locks(keys)["A"], locks[1])

    @patch("samcli.lib.utils.lock_distributor.threading.Lock")
    @patch("samcli.lib.utils.lock_distributor.multiprocessing.Lock")
    def test_process_manager_get_locks(self, process_lock_mock, thread_lock_mock):
        manager_mock = MagicMock()
        locks = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
        manager_mock.dict.return_value = dict()
        manager_mock.Lock.side_effect = locks
        distributor = LockDistributor(LockDistributorType.PROCESS, manager_mock)
        keys = ["A", "B", "C"]
        result = distributor.get_locks(keys)

        self.assertEqual(result["A"], locks[1])
        self.assertEqual(result["B"], locks[2])
        self.assertEqual(result["C"], locks[3])
        self.assertEqual(distributor.get_locks(keys)["A"], locks[1])
