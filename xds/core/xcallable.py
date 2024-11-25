from typing import Any, Callable, Dict, List

from pydantic import BaseModel


class XCallable(BaseModel):
    ns: str
    args: List[Any] = []
    kwargs: Dict[str, Any] = {}
    fn: Callable = None

    def __init__(
        self,
        ns: str,
        args: List[Any] | None = None,
        kwargs: Dict[str, Any] | None = None,
    ):
        super().__init__(ns=ns, args=args or [], kwargs=kwargs or {})

    def __call__(self) -> Any:
        ret_type = self.kwargs.get('rtype', Any)
        xret = self.fn(self.ns, *self.args, **self.kwargs)
        if not isinstance(xret, ret_type):
            raise TypeError(
                f'Expected a {ret_type.__name__}, got {type(xret).__name__}'
            )
        return xret
