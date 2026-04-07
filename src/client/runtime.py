import os
import sys


def get_runtime_root():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resolve_runtime_path(*parts):
    return os.path.join(get_runtime_root(), *parts)
