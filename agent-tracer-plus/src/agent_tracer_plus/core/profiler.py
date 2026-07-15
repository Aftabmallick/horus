import inspect
import sys
import threading
from typing import Any, Dict, List, Optional, Set

from agent_tracer_plus.core.context import SpanContext, get_tracer
from agent_tracer_plus.core.models import SpanType
from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("core.profiler")


class SysProfiler:
    """Hooks into the Python runtime to automatically trace specified modules."""

    def __init__(self) -> None:
        self.target_modules: tuple[str, ...] = ()
        self._active = False
        self._is_sys_mon = False
        
        # Tool ID for Python 3.12+ sys.monitoring
        self._tool_id: Optional[int] = None
        
        # Map frame IDs to SpanContexts. This perfectly handles async interleaving
        # because each function invocation (even across suspensions) has a unique frame ID.
        self._frame_spans: Dict[int, SpanContext] = {}

    def start(self, target_modules: List[str]) -> None:
        """Start profiling specific module prefixes."""
        if self._active or not target_modules:
            return

        self.target_modules = tuple(target_modules)
        self._active = True

        # Try to use PEP 669 sys.monitoring (Python 3.12+)
        if sys.version_info >= (3, 12):
            try:
                import sys.monitoring as sm
                
                # We need an available tool ID (0 to 5 are allowed)
                self._tool_id = sm.PROFILER_ID
                sm.use_tool_id(self._tool_id, "agent_tracer_plus")
                
                sm.register_callback(self._tool_id, sm.events.PY_START, self._mon_py_start)
                sm.register_callback(self._tool_id, sm.events.PY_RETURN, self._mon_py_return)
                sm.register_callback(self._tool_id, sm.events.PY_UNWIND, self._mon_py_return)
                
                sm.set_events(self._tool_id, sm.events.PY_START | sm.events.PY_RETURN | sm.events.PY_UNWIND)
                
                self._is_sys_mon = True
                logger.info(f"SysProfiler started using PEP 669 sys.monitoring for modules: {self.target_modules}")
                return
            except Exception as e:
                logger.warning(f"Failed to activate sys.monitoring, falling back to sys.setprofile: {e}")

        # Fallback to sys.setprofile for Python < 3.12
        sys.setprofile(self._profile_callback)
        threading.setprofile(self._profile_callback)
        logger.info(f"SysProfiler started using sys.setprofile for modules: {self.target_modules}")

    def stop(self) -> None:
        """Stop profiling and remove hooks."""
        if not self._active:
            return

        if self._is_sys_mon and self._tool_id is not None:
            import sys.monitoring as sm
            sm.set_events(self._tool_id, 0)
            sm.free_tool_id(self._tool_id)
        else:
            sys.setprofile(None)
            threading.setprofile(None)

        self._active = False
        self._frame_spans.clear()
        logger.info("SysProfiler stopped.")

    # ---------------------------------------------------------
    # Python 3.12+ PEP 669 Callbacks
    # ---------------------------------------------------------

    def _mon_py_start(self, code: Any, instruction_offset: int) -> None:
        """Callback for function entry in sys.monitoring."""
        try:
            frame = sys._getframe(1)
            mod_name = frame.f_globals.get("__name__", "")
            if mod_name.startswith(self.target_modules):
                func_name = code.co_name
                span = SpanContext(name=f"{mod_name}.{func_name}", span_type=SpanType.TOOL)
                span.__enter__()
                self._frame_spans[id(frame)] = span
        except Exception:
            pass
            
    def _mon_py_return(self, code: Any, instruction_offset: int, retval: Any) -> None:
        """Callback for function exit in sys.monitoring."""
        try:
            frame = sys._getframe(1)
            span = self._frame_spans.pop(id(frame), None)
            if span:
                span.span.output = str(retval)
                span.__exit__(None, None, None)
        except Exception:
            pass

    # ---------------------------------------------------------
    # Python < 3.12 sys.setprofile Callback
    # ---------------------------------------------------------

    def _profile_callback(self, frame: Any, event: str, arg: Any) -> None:
        """Standard sys.setprofile callback."""
        if event not in ("call", "return", "c_call", "c_return", "c_exception"):
            return

        mod_name = frame.f_globals.get("__name__", "")
        if not mod_name or not mod_name.startswith(self.target_modules):
            return

        if event in ("call", "c_call"):
            func_name = frame.f_code.co_name if event == "call" else arg.__name__
            span = SpanContext(name=f"{mod_name}.{func_name}", span_type=SpanType.TOOL)
            span.__enter__()
            self._frame_spans[id(frame)] = span

        elif event in ("return", "c_return", "c_exception"):
            span = self._frame_spans.pop(id(frame), None)
            if span:
                if event == "return":
                    span.span.output = str(arg)
                span.__exit__(None, None, None)
