"""状态注册表：识别当前界面 + 转移图 BFS 寻路。"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence

from fsm.state import State

# priority >= 此值的 State 视为弹框/异常，任何时候都优先检查
POPUP_PRIORITY = 100


class StateRegistry:
    """注册所有 State 并提供识别与寻路。"""

    def __init__(self, flow_name: str = "") -> None:
        self.flow_name = flow_name
        self._states: list[State] = []
        self._edges: dict[type[State], list[type[State]]] = {}
        self._instances: dict[type[State], State] = {}
        self.reset_flow = None  # 每轮开始时的重置回调，由流程设置

    def register(self, state: State, transitions: Sequence[type[State]] = ()) -> None:
        """注册一个 State 实例及其可达的下一界面类型。"""
        if self.flow_name:
            state.flow_name = self.flow_name
        self._states.append(state)
        self._edges[type(state)] = list(transitions)
        self._instances[type(state)] = state

    def identify(self, ctx, *, expected: type[State] | None = None) -> State | None:
        """识别当前界面，返回首个命中的 State。

        弹框（priority >= POPUP_PRIORITY）始终优先检查。
        expected 非空时，优先检查该类型；不匹配才降级为全量识别。

        Args:
            ctx: 执行上下文。
            expected: 期望进入的 State 类型（来自上一轮的 Goto 信号）。

        Returns:
            命中的 State 实例，或 None。
        """
        sorted_states = sorted(self._states, key=lambda s: -s.priority)

        # 1. 弹框始终优先（自愈机制）
        for state in sorted_states:
            if state.priority >= POPUP_PRIORITY and state.match(ctx):
                return state

        # 2. 期望状态优先
        if expected is not None:
            for state in sorted_states:
                if isinstance(state, expected) and state.match(ctx):
                    return state
            # 期望状态未匹配 → 返回 None，由引擎决定重试还是降级
            return None

        # 3. 全量识别（无期望状态时）
        for state in sorted_states:
            if state.match(ctx):
                return state
        return None

    def get_instance(self, state_type: type[State]) -> State:
        """获取已注册的 State 实例（用于修改内部状态）。"""
        return self._instances[state_type]

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
