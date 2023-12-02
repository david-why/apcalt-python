class BusinessError(RuntimeError):
    __slots__ = 'code', 'msg'

    def __init__(self, code: int = 500, msg: str | None = None, *args):
        self.code = code
        self.msg = msg
        super().__init__(*args)
