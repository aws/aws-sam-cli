"""LockDistributor for creating and managing a set of locks"""

import multiprocessing
import multiprocessing.managers
import threading
from enum import Enum, auto
from typing import Dict, Optional, Set, cast


class LockChain:
    """Wrapper class for acquiring multiple locks in the same order to prevent dead locks
    Can be used with `with` statement"""

    def __init__(self, lock_mapping: Dict[str, threading.Lock]):
        """
        Parameters
        ----------
        lock_mapping : Dict[str, threading.Lock]
            Dictionary of locks with keys being used as generating reproduciable order for aquiring and releasing locks.
        """
        self._locks = [value for _, value in sorted(lock_mapping.items())]

    def acquire(self) -> None:
        """Aquire all locks in the LockChain"""
        for lock in self._locks:
            lock.acquire()

    def release(self) -> None:
        """Release all locks in the LockChain"""
        for lock in self._locks:
            lock.release()

    def __enter__(self) -> "LockChain":
        self.acquire()
        return self

    def __exit__(self, exception_type, exception_value, traceback) -> None:
        self.release()


class LockDistributorType(Enum):
    """Types of LockDistributor"""

    THREAD = auto()
    PROCESS = auto()


class LockDistributor:
    """Dynamic lock distributor that supports threads and processes.
    In the case of processes, both manager(server process) or shared memory can be used.
    """

    _lock_type: LockDistributorType
    _manager: Optional[multiprocessing.managers.SyncManager]
    _dict_lock: threading.Lock
    _locks: Dict[str, threading.Lock]

    def __init__(
        self,
        lock_type: LockDistributorType = LockDistributorType.THREAD,
        manager: Optional[multiprocessing.managers.SyncManager] = None,
    ):
        """[summary]

        Parameters
        ----------
        lock_type : LockDistributorType, optional
            Whether locking with threads or processes, by default LockDistributorType.THREAD
        manager : Optional[multiprocessing.managers.SyncManager], optional
            Optional process sync mananger for creating proxy locks, by default None
        """
        self._lock_type = lock_type
        self._manager = manager
        self._dict_lock = self._create_new_lock()
        self._locks = (
            self._manager.dict()  # type: ignore
            if self._lock_type == LockDistributorType.PROCESS and self._manager is not None
            else dict()
        )

    def _create_new_lock(self) -> threading.Lock:
        """Create a new lock based on lock type

        Returns
        -------
        threading.Lock
            Newly created lock
        """
        if self._lock_type == LockDistributorType.THREAD:
            return threading.Lock()

        return self._manager.Lock() if self._manager is not None else cast(threading.Lock, multiprocessing.Lock())

    def get_lock(self, key: str) -> threading.Lock:
        """Retrieve a lock associating with the key
        If the lock does not exist, a new lock will be created.

        Parameters
        ----------
        key : Key for retrieving the lock

        Returns
        -------
        threading.Lock
            Lock associated with the key
        """
        with self._dict_lock:
            if key not in self._locks:
                self._locks[key] = self._create_new_lock()
            return self._locks[key]

    def get_locks(self, keys: Set[str]) -> Dict[str, threading.Lock]:
        """Retrieve a list of locks associating with keys

        Parameters
        ----------
        keys : Set[str]
            Set of keys for retrieving the locks

        Returns
        -------
        Dict[str, threading.Lock]
            Dictionary mapping keys to locks
        """
        lock_mapping = dict()
        for key in keys:
            lock_mapping[key] = self.get_lock(key)
        return lock_mapping

    def get_lock_chain(self, keys: Set[str]) -> LockChain:
        """Similar to get_locks, but retrieves a LockChain object instead of a dictionary

        Parameters
        ----------
        keys : Set[str]
            Set of keys for retrieving the locks

        Returns
        -------
        LockChain
            LockChain object containing all the locks associated with keys
        """
        return LockChain(self.get_locks(keys))
