import uuid
import time
from typing import Dict, Any, Optional
from threading import Lock
from dataclasses import dataclass, field, asdict

@dataclass
class TaskInfo:
    id: str
    status: str  # PENDING, RUNNING, COMPLETED, FAILED
    tool: str
    params: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    def to_dict(self):
        return asdict(self)

class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, TaskInfo] = {}
        self.lock = Lock()

    def create_task(self, tool_name: str, params: Dict[str, Any]) -> str:
        task_id = str(uuid.uuid4())
        task = TaskInfo(
            id=task_id,
            status="PENDING",
            tool=tool_name,
            params=params
        )
        with self.lock:
            self.tasks[task_id] = task
        return task_id

    def update_task(self, task_id: str, status: str, result: Any = None, error: str = None):
        with self.lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                task.status = status
                if result is not None:
                    task.result = result
                if error is not None:
                    task.error = error
                if status in ["COMPLETED", "FAILED"]:
                    task.end_time = time.time()

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            task = self.tasks.get(task_id)
            if task:
                return task.to_dict()
        return None

# Global instance
task_manager = TaskManager()
