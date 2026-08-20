from provium import ProcedureCatalog

from .tokenize.definition import TOKENIZE

catalog = ProcedureCatalog()
catalog.register(TOKENIZE)

__all__ = ["TOKENIZE", "catalog"]
