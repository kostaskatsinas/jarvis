"""Agent packages. Each subpackage registers its agent on import;
load_agents() discovers and imports all of them at startup."""

import importlib
import pkgutil


def load_agents() -> None:
    for module in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{__name__}.{module.name}")
