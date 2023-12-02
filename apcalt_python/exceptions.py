class BusinessError(RuntimeError):
    __slots__ = 'msg', 'code'

    def __init__(self, msg: str | None = None, code: int = 500, *args):
        self.msg = msg
        self.code = code
        super().__init__(*args)
