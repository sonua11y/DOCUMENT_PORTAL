import sys
import traceback
class DocumentPortalException(Exception):
    def __init__(self, error_message, error_details):
        exc_info = None
        if hasattr(error_details, "exc_info") and callable(getattr(error_details, "exc_info")):
            try:
                exc_info = error_details.exc_info()
            except Exception:
                exc_info = None

        if not exc_info and isinstance(error_details, BaseException):
            exc_info = (type(error_details), error_details, error_details.__traceback__)

        _, _, exc_tb = exc_info or (None, None, None)
        
        # Handle case when exc_tb is None (no active exception)
        if exc_tb is not None:
            self.file_name = exc_tb.tb_frame.f_code.co_filename
            self.lineno = exc_tb.tb_lineno
            if exc_info:
                self.traceback_str = ''.join(traceback.format_exception(*exc_info))
            else:
                self.traceback_str = f"No traceback available. Error: {error_message}"
        else:
            # Fallback when no active exception traceback
            import inspect
            frame = inspect.currentframe()
            if frame and frame.f_back:
                self.file_name = frame.f_back.f_code.co_filename
                self.lineno = frame.f_back.f_lineno
            else:
                self.file_name = "unknown"
                self.lineno = 0
            self.traceback_str = f"No traceback available. Error: {error_message}"
        
        self.error_message = str(error_message)

    def __str__(self):
        return f"""
        Error in [{self.file_name}] at line [{self.lineno}]
        Message: {self.error_message}
        Traceback:
        {self.traceback_str}
        """

if __name__ == "__main__":
    try:
        a = 1 / 0  # deliberate error
    except Exception as e:
        app_exc = DocumentPortalException(e, sys)
        #logger.error(app_exc)  # log it to file
        raise app_exc  # propagate with full traceback
    # try:
    #     a = int("abc")  # ValueError (inbuilt)
    # except ValueError as e:
    #     raise DocumentPortalException("Failed while processing document", e)