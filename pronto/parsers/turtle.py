import rdflib
import os

from .base import BaseParser

class TurtleParser(BaseParser):

    @classmethod
    def can_parse(cls, path, buffer):
        return buffer.lstrip().startswith((b"<?ttl", b"<?n3"))

    def parse_from(self, handle):
        graph = rdflib.Graph()
        doc = graph.parse(handle)
        
        self.ont.imports.update(
            self.process_imports(
                doc,
                self.ont.import_depth,
                os.path.dirname(self.ont.path or str()),
                self.ont.timeout,
            )
        )
