import sys


class GreenFleetException(Exception):

    def __init__(self, error_message, error_details: sys):

        self.error_message = error_message

        _, _, exc_tb = error_details.exc_info()

        self.lineno = exc_tb.tb_lineno

        self.file_name = exc_tb.tb_frame.f_code.co_filename

    def __str__(self):

        return (
            f"Error occurred in python script "
            f"[{self.file_name}] "
            f"line number [{self.lineno}] "
            f"error message [{self.error_message}]"
        )