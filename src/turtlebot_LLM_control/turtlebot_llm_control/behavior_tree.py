from enum import Enum
from typing import Callable, Iterable, List


class NodeStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


class BTNode:
    def tick(self) -> NodeStatus:
        raise NotImplementedError


class ConditionNode(BTNode):
    def __init__(self, fn: Callable[[], bool]):
        self._fn = fn

    def tick(self) -> NodeStatus:
        return NodeStatus.SUCCESS if self._fn() else NodeStatus.FAILURE


class ActionNode(BTNode):
    def __init__(self, fn: Callable[[], NodeStatus]):
        self._fn = fn

    def tick(self) -> NodeStatus:
        return self._fn()


class SequenceNode(BTNode):
    def __init__(self, children: Iterable[BTNode]):
        self._children: List[BTNode] = list(children)

    def tick(self) -> NodeStatus:
        for child in self._children:
            result = child.tick()
            if result != NodeStatus.SUCCESS:
                return result
        return NodeStatus.SUCCESS


class FallbackNode(BTNode):
    def __init__(self, children: Iterable[BTNode]):
        self._children: List[BTNode] = list(children)

    def tick(self) -> NodeStatus:
        for child in self._children:
            result = child.tick()
            if result in {NodeStatus.SUCCESS, NodeStatus.RUNNING}:
                return result
        return NodeStatus.FAILURE
