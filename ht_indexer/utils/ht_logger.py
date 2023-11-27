import logging
import sys
import datetime
import os


class HTLogger(logging.getLoggerClass()):
    def __init__(self, name, log_dir=None, set_level=logging.DEBUG):
        # Create custom logger logging all five levels
        super().__init__(name)
        self.setLevel(set_level)

        # Create stream handler for logging to stdout
        self.stdout_handler = logging.StreamHandler(sys.stdout)
        self.stdout_handler.setLevel(set_level)
        self.stdout_handler.setFormatter(logging.Formatter("%(message)s"))
        # self.enable_console_output()

        # Add file handler only if the log directory was specified
        self.file_handler = None
        if log_dir:
            self.add_file_handler(name, log_dir)

    def add_file_handler(self, name, log_dir):
        """Add a file handler for this logger with the specified `name` (and
        store the log file under `log_dir`)."""

        # Format for file log
        fmt = "%(asctime)s | %(levelname)8s | %(filename)s:%(lineno)d | %(message)s"
        formatter = logging.Formatter(fmt)

        # Determine log path/file name; create log_dir if necessary
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_name = f'{str(name).replace(" ", "_")}_{now}'
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir)
            except:
                print(
                    "{}: Cannot create directory {}. ".format(
                        self.__class__.__name__, log_dir
                    ),
                    end="",
                    file=sys.stderr,
                )
                log_dir = "/tmp" if sys.platform.startswith("linux") else "."
                print(f"Defaulting to {log_dir}.", file=sys.stderr)

        log_file = os.path.join(log_dir, log_name) + ".log"

        # Create file handler for logging to a file (log all five levels)
        self.file_handler = logging.FileHandler(log_file)
        self.file_handler.setLevel(self.level)
        self.file_handler.setFormatter(formatter)
        self.addHandler(self.file_handler)
