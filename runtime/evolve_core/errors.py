class EvolveError(Exception):
    def __init__(self, code, message, *, exit_code=2, next_steps=(), committed=False):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.next_steps = list(next_steps)
        self.committed = committed
