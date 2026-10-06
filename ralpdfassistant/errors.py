#свои ошибки, дальше в http


class AppError(Exception):
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(AppError):
    status_code = 404


class TooLarge(AppError):
    status_code = 413


class LlmUnavailable(AppError):
    status_code = 502
