import time
import random
import threading
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dag_scheduler")


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class Task:
    id: str
    name: str
    func: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 3
    timeout: float = 30.0


@dataclass
class DAG:
    id: str
    name: str
    tasks: Dict[str, Task] = field(default_factory=dict)


class DAGScheduler:
    def __init__(self):
        self.dags: Dict[str, DAG] = {}
        self.providers: Dict[str, Any] = {}
        self.failure_counts: Dict[str, int] = {}
        self.circuit_breaker: Dict[str, datetime] = {}
        self.concurrency_limit = 3
        self.priority_weights = {"groq": 3, "local": 2, "huggingface": 1}

    def register_dag(self, dag: DAG):
        visited = set()
        path = set()

        def dfs(task_id):
            if task_id in path:
                raise ValueError(f"Cycle detected involving {task_id}")
            if task_id in visited:
                return
            visited.add(task_id)
            path.add(task_id)
            for dep in dag.tasks[task_id].dependencies:
                dfs(dep)
            path.remove(task_id)

        for task_id in dag.tasks:
            dfs(task_id)

        self.dags[dag.id] = dag
        logger.info(f"Registered DAG: {dag.name}")

    def register_provider(self, name: str, provider_instance):
        self.providers[name] = provider_instance
        self.failure_counts[name] = 0

    def execute_dag(self, dag_id: str) -> Dict[str, Any]:
        dag = self.dags.get(dag_id)
        if not dag:
            raise ValueError(f"DAG {dag_id} not found")

        results = {}
        completed = set()
        failed = set()

        while len(completed) + len(failed) < len(dag.tasks):
            ready = self._get_ready_tasks(dag, completed, failed)
            if not ready:
                if len(completed) + len(failed) < len(dag.tasks):
                    logger.warning("No ready tasks — possible deadlock")
                break

            threads = []
            for task in ready[:self.concurrency_limit]:
                t = threading.Thread(target=self._execute_task, args=(task, dag, results, completed, failed))
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            time.sleep(0.1)

        return {
            "success": len(failed) == 0,
            "results": results,
            "failed": list(failed)
        }

    def _get_ready_tasks(self, dag, completed, failed):
        ready = []
        for task_id, task in dag.tasks.items():
            if task_id in completed or task_id in failed:
                continue
            if task.status in (TaskStatus.RUNNING, TaskStatus.SUCCESS):
                continue
            if all(dep in completed for dep in task.dependencies):
                ready.append(task)
        return ready

    def _execute_task(self, task, dag, results, completed, failed):
        task.status = TaskStatus.RUNNING

        provider_name = self._select_provider()
        if not provider_name:
            logger.error(f"No provider for {task.id}")
            task.status = TaskStatus.FAILED
            task.error = "No healthy provider"
            failed.add(task.id)
            return

        provider = self.providers[provider_name]
        logger.info(f"Executing {task.id} on {provider_name}")

        try:
            start = time.time()
            result = task.func(provider, *task.args, **task.kwargs)
            task.result = result
            task.status = TaskStatus.SUCCESS
            results[task.id] = result
            completed.add(task.id)
            self.failure_counts[provider_name] = 0
            logger.info(f"{task.id} done in {time.time()-start:.2f}s via {provider_name}")
        except Exception as e:
            if task.retries < task.max_retries:
                task.retries += 1
                task.status = TaskStatus.RETRY
                logger.warning(f"{task.id} retry {task.retries}/{task.max_retries}: {e}")
                self.failure_counts[provider_name] = self.failure_counts.get(provider_name, 0) + 1
                if self.failure_counts[provider_name] >= 3:
                    self.circuit_breaker[provider_name] = datetime.now() + timedelta(minutes=5)
            else:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                failed.add(task.id)
                logger.error(f"{task.id} failed after {task.max_retries} retries: {e}")

    def _select_provider(self) -> Optional[str]:
        healthy = []
        for name in self.providers:
            if name in self.circuit_breaker and datetime.now() < self.circuit_breaker[name]:
                continue
            if self.failure_counts.get(name, 0) < 3:
                healthy.append(name)

        if not healthy:
            return None

        weights = [self.priority_weights.get(p, 1) for p in healthy]
        return random.choices(healthy, weights=weights, k=1)[0]
