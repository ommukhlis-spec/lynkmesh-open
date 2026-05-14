# core/ir_core.py
"""
IR Core – Defines the stable Intermediate Representation contracts
consumed by GraphBuilder, CallResolver, and all analysis engines.
"""
from typing import TypedDict, List, Dict, Optional, Any


class IRCall(TypedDict, total=False):
    method: str
    class_: Optional[str]          # called class (if known)
    line: Optional[int]
    assign_to: Optional[str]       # variable that receives the result


class IRMethod(TypedDict, total=False):
    name: str
    visibility: str
    params: List[Dict[str, Any]]
    return_type: Optional[str]
    file: str
    calls: List[IRCall]
    function_calls: List[IRCall]
    instantiations: List[Dict[str, Any]]
    assignments: List[Dict[str, Any]]
    property_fetches: List[Dict[str, Any]]
    static_property_fetches: List[Dict[str, Any]]
    constant_fetches: List[Dict[str, Any]]
    returns: List[Dict[str, Any]]
    sql_strings: List[str]
    has_try_catch: bool


class IRClass(TypedDict, total=False):
    name: str
    fqn: Optional[str]
    extends: Optional[str]
    implements: List[str]
    traits: List[str]
    methods: List[IRMethod]
    properties: List[Dict[str, Any]]


class IRFunction(TypedDict, total=False):
    name: str
    fqn: Optional[str]
    file: str
    params: List[Dict[str, Any]]
    return_type: Optional[str]
    calls: List[IRCall]
    http_method: Optional[str]
    uri: Optional[str]
    controller: Optional[str]
    controller_method: Optional[str]


class IRFile(TypedDict, total=False):
    file: str
    namespace: Optional[str]
    uses: List[str]
    method_return_types: Dict[str, str]
    classes: List[IRClass]
    functions: List[IRFunction]