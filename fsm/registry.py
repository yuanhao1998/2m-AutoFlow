"""状态注册表：识别当前界面 + 转移图 BFS 寻路。"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence

from fsm.state import State


class StateRegistry:
    """注册所有 State 并提供识别与寻路。"""

    def __init__(self, flow_name: str = "") -> None:
        self.flow_name = flow_name
        self._states: list[State] = []
        self._edges: dict[type[State], list[type[State]]] = {}

    def register(self, state: State, transitions: Sequence[type[State]] = ()) -> None:
        """注册一个 State 实例及其可达的下一界面类型。"""
        if self.flow_name:
            state.flow_name = self.flow_name
        self._states.append(state)
        self._edges[type(state)] = list(transitions)

    def identify(self, ctx) -> State | None:
        """按 priority 降序返回首个命中的 State；均不命中返回 None。"""
        for state in sorted(self._states, key=lambda s: -s.priority):
            if state.match(ctx):
                return state
        return None

    def find_path(self, start: type[State], target: type[State]) -> list[type[State]] | None:
        """转移图 BFS：返回从 start 到 target 的路径（不含 start）。

        start==target 返回 []；不可达返回 None。
        """
        if start is target:
            return []
        visited = {start}
        queue: deque[tuple[type[State], list[type[State]]]] = deque([(start, [])])
        while queue:
            node, path = queue.popleft()
            for nxt in self._edges.get(node, []):
                if nxt in visited:
                    continue
                new_path = path + [nxt]
                if nxt is target:
                    return new_path
                visited.add(nxt)
                queue.append((nxt, new_path))
        return None
