import io
import os
import unittest
import warnings

import pronto
import rdflib

class TestTurtleReading(unittest.TestCase):

    @staticmethod
    def get_ontology(content):
        return pronto.Ontology(content)

    def test_ontology(self):
        ont = self.get_ontology("http://purl.bioontology.org/ontology/ICD10CM/P00-P96")
        self.assertEqual(len(ont.terms()), 245)