import multiprocessing
import os

import flet as ft

from qrstudio.ui import main


if __name__ == "__main__":
    multiprocessing.freeze_support()
    if os.environ.get("QRSTUDIO_WEB") == "1":
        os.environ["FLET_FORCE_WEB_SERVER"]="1"
        ft.run(main,view=None,port=int(os.environ.get("QRSTUDIO_PORT","8550")),host="127.0.0.1")
    else:
        ft.run(main)
