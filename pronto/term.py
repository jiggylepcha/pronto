import datetime
import typing
import weakref
from typing import Callable, Dict, List, Optional, Set, Tuple, Union, FrozenSet

import fastobo

from .entity import Entity
from .definition import Definition
from .xref import Xref
from .synonym import Synonym, _SynonymData
from .relationship import Relationship
from .pv import PropertyValue, ResourcePropertyValue, LiteralPropertyValue
from .utils.repr import make_repr

if typing.TYPE_CHECKING:
    from .ontology import Ontology


class _TermData():  # noqa: R0902, R0903
    """Internal data storage of `Term` information.
    """

    id: str
    anonymous: bool
    name: Optional[str]
    alternate_ids: Set[str]
    definition: Optional[Definition]
    comment: Optional[str]
    synonyms: Set[_SynonymData]
    subsets: Set[str]
    namespace: Optional[str]
    xrefs: Set[Xref]
    intersection_of: Set[Union[str, Tuple[str, str]]]
    union_of: Set[str]
    disjoint_from: Set[str]
    relationships: Dict[str, Set[str]]
    obsolete: bool
    replaced_by: Set[str]
    consider: Set[str]
    builtin: bool
    created_by: Optional[str]
    creation_date: Optional[datetime.datetime]
    equivalent_to: Set[str]
    annotations: Set[PropertyValue]

    __slots__ = ("__weakref__",) + tuple(__annotations__)  # noqa: E0602

    def __init__(
        self,
        id,
        anonymous=False,
        name=None,
        alternate_ids=None,
        definition=None,
        comment=None,
        synonyms=None,
        subsets=None,
        namespace=None,
        xrefs=None,
        intersection_of=None,
        union_of=None,
        disjoint_from=None,
        relationships=None,
        obsolete=False,
        replaced_by=None,
        consider=None,
        builtin=False,
        created_by=None,
        creation_date=None,
        equivalent_to=None,
        annotations=None,
    ):
        self.id = id
        self.anonymous = anonymous
        self.name = name
        self.alternate_ids = alternate_ids or set()
        self.definition = definition
        self.comment = comment
        self.synonyms = synonyms or set()
        self.subsets = subsets or set()
        self.namespace = namespace or None
        self.xrefs = xrefs or set()
        self.intersection_of = intersection_of or set()
        self.union_of = union_of or set()
        self.disjoint_from = disjoint_from or set()
        self.relationships = relationships or dict()
        self.obsolete = obsolete
        self.replaced_by = replaced_by or set()
        self.consider = consider or set()
        self.builtin = builtin
        self.created_by = created_by
        self.creation_date = creation_date
        self.equivalent_to = equivalent_to or set()
        self.annotations = annotations or set()


class Term(Entity):
    """A term, corresponding to a node in the ontology graph.
    """

    def __init__(self, ontology: 'Ontology', termdata: '_TermData'):
        """Instantiate a new `Term`.

        Important:
            Do not use directly, as this API does some black magic to reduce
            memory usage and improve consistentcy in the data model. Use
            `Ontology.create_term` or `Ontology.get_term` depending on your
            needs to obtain a `Term` instance.    
        """
        self._ontology = weakref.ref(ontology)
        self._data = weakref.ref(termdata)

    @classmethod
    def _from_ast(cls, frame: fastobo.term.TermFrame, ontology: 'Ontology'):

        term = ontology.create_term(str(frame.id))
        termdata = term._data()

        union_of = set()
        intersection_of = set()

        def copy(src, dst=None, cb=None):
            cb = cb or (lambda x: x)
            dst = dst or src
            return lambda c: setattr(term, dst, cb(getattr(c, src)))

        def add(src, dst=None, cb=None):
            cb = cb or (lambda x: x)
            dst = dst or src
            return lambda c: getattr(termdata, dst).add(cb(getattr(c, src)))

        def todo():
            return lambda c: print("todo", c)

        _callbacks = {
            fastobo.term.IsAnonymousClause: copy("anonymous"),
            fastobo.term.NameClause: copy("name"),
            fastobo.term.DefClause:
                lambda c: setattr(term, "definition", Definition._from_ast(c)),
            fastobo.term.AltIdClause: add("alt_id", "alternate_ids", cb=str),
            fastobo.term.IntersectionOfClause: lambda c: (
                intersection_of.add((str(c.typedef), str(c.term)))
                if c.typedef is not None
                else intersection_of.add(str(c.term))
            ),
            fastobo.term.UnionOfClause: lambda c: union_of.add(str(c.term)),
            fastobo.term.RelationshipClause:
                lambda c: termdata.relationships.setdefault(str(c.typedef), set()).add(str(c.term)),
            fastobo.term.BuiltinClause: copy("builtin"),
            fastobo.term.CommentClause: copy("comment"),
            fastobo.term.ConsiderClause: add("term", "consider", cb=str),
            fastobo.term.CreatedByClause: copy("creator", "created_by"),
            fastobo.term.CreationDateClause: copy("date", "creation_date"),
            fastobo.term.EquivalentToClause: add("equivalent_to", cb=str),
            fastobo.term.IsAClause:
                lambda c: termdata.relationships.setdefault("is_a", set()).add(str(c.term)),
            fastobo.term.IsObsoleteClause: copy("obsolete"),
            fastobo.term.NamespaceClause: copy("namespace", cb=str),
            fastobo.term.SubsetClause: add("subset", "subsets", cb=str),
            fastobo.term.SynonymClause:
                lambda c: termdata.synonyms.add(_SynonymData._from_ast(c.synonym)),
            fastobo.term.DisjointFromClause: add("term", "disjoint_from", cb=str),
            fastobo.term.PropertyValueClause: (lambda c: (
                termdata.annotations.add(
                    PropertyValue._from_ast(c.property_value)
                )
            )),
            fastobo.term.ReplacedByClause: add("term", "replaced_by", cb=str),
            fastobo.term.XrefClause: add("xref", "xrefs", cb=Xref._from_ast),
        }

        for clause in frame:
            try:
                _callbacks[type(clause)](clause)
            except KeyError:
                raise TypeError(f"unexpected type: {type(clause).__name__}")
        if len(union_of) == 1:
            raise ValueError("'union_of' cannot have a cardinality of 1")
        termdata.union_of = union_of
        if len(intersection_of) == 1:
            raise ValueError("'intersection_of' cannot have a cardinality of 1")
        termdata.intersection_of = intersection_of
        return term

    def _to_ast(self) -> fastobo.term.TermFrame:
        frame = fastobo.term.TermFrame(fastobo.id.parse(self.id))
        if self.anonymous:
            frame.append(fastobo.term.IsAnonymousClause(True))
        if self.name is not None:
            frame.append(fastobo.term.NameClause(self.name))
        if self.namespace is not None:
            ns = fastobo.id.parse(self.namespace)
            frame.append(fastobo.term.NamespaceClause(ns))
        for id in sorted(self.alternate_ids):
            frame.append(fastobo.term.AltIdClause(fastobo.id.parse(id)))
        if self.definition is not None:
            frame.append(self.definition._to_ast())
        if self.comment is not None:
            frame.append(fastobo.term.CommentClause(self.comment))
        for subset in sorted(self.subsets):
            frame.append(fastobo.term.SubsetClause(fastobo.id.parse(subset)))
        for synonym in sorted(self.synonyms):
            frame.append(fastobo.term.SynonymClause(synonym._to_ast()))
        for xref in sorted(self.xrefs):
            frame.append(fastobo.term.XrefClause(xref._to_ast()))
        if self.builtin:
            frame.append(fastobo.term.BuiltinClause(True))
        # for annotations in self.annotations:
        #     pass # TODO
        for other in sorted(self.relationships.get('is_a', ())): # FIXME
            frame.append(fastobo.term.IsAClause(fastobo.id.parse(other.id)))
        # for other in sorted(self.intersection_of):
        #     pass # TODO
        for member in sorted(self.union_of):
            frame.append(fastobo.term.UnionOfClause(member))

        return frame

    @property
    def disjoint_from(self) -> Set['Term']:
        ontology, termdata = self._ontology(), self._data()
        return {
            Term(ontology, ontology.get_term(id))
            for id in termdata.disjoint_from
        }

    @property
    def relationships(self) -> Dict[Relationship, FrozenSet['Term']]:
        ont, termdata = self._ontology(), self._data()
        return {
            Relationship(ont, ont.get_relationship(rel)._data()): frozenset(
                Term(ont, ont.get_term(term)._data())
                for term in terms
            )
            for rel,terms in termdata.relationships.items()
        }

    @property
    def union_of(self) -> Set['Term']:
        cls, termdata, ont = type(self), self._data(), self._ontology()
        return {cls(ont, id) for id in termdata.union_of}

    @union_of.setter
    def union_of(self, union_of: Set['Term']):
        if __debug__:
            if not isinstance(union_of, set) or any(not isinstance(x, Term) for x in union_of):
                msg = "'union_of' must be a set of Terms, not {}"
                raise TypeError(msg.format(type(union_of).__name__))
        if len(union_of) == 1:
            raise ValueError("'union_of' cannot have a cardinality of 1")
        self._data().union_of = {term.id for term in union_of}

    @property
    def consider(self) -> FrozenSet['Term']:
        cls, termdata, ont = type(self), self._data(), self._ontology()
        return frozenset(cls(ont, id) for id in termdata.consider)
