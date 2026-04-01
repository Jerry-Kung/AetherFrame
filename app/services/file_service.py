import os

DATA_DIR = os.getenv("DATA_DIR", "./data")


def read_hello_file() -> tuple[bool, str]:
    file_path = os.path.join(DATA_DIR, "hello.txt")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return True, content
    except Exception as e:
        return False, str(e)
