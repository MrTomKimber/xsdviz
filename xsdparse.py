"""
xsdparse
===========

A utility for parsing an xsd and producing a model specification.

"""
import xmltodict
import zipfile
from collections import Counter
import os, sys
#sys.path.append(os.path.abspath(".."))
import treepath.treepath as tp

import pandas as pd
import networkx as nx


def key_scan_obj(obj, search=None, path=None, results=None):
    if results is None:
        results = []
    if search is None:
        search = None
    if path is None:
        path = []
    if isinstance(obj, dict):
        for k,v in obj.items():
            if (k==search or v==search):
                results.append({"path" : path+[k], "value" : v})
            elif isinstance(v, (dict, list)):
                results.extend(key_scan_obj(v, search=search, path=path + [k]))
    elif isinstance(obj, list):
        for e,v in enumerate(obj):
            if v==search:
                results.append({"path" : path+[e], "value" : v})
            elif isinstance(v, (dict, list)):
                results.extend(key_scan_obj(v, search=search, path = path + [e]))
    else:
        if v==search or search is None:
            results.append({"path" : path, "value" : v})
    return results

prims=[ {'@name': 'xs:duration'},
        {'@name': 'xs:dateTime'},
        {'@name': 'xs:time'},
        {'@name': 'xs:date'},
        {'@name': 'xs:gYearMonth'},
        {'@name': 'xs:gYear'},
        {'@name': 'xs:gMonthDay'},
        {'@name': 'xs:gDay'},
        {'@name': 'xs:gMonth'},
        {'@name': 'xs:string'},
        {'@name': 'xs:boolean'},
        {'@name': 'xs:base64Binary'},
        {'@name': 'xs:hexBinary'},
        {'@name': 'xs:float'},
        {'@name': 'xs:decimal'},
        {'@name': 'xs:integer'},
        {'@name': 'xs:nonPositiveInteger'},
        {'@name': 'xs:negativeInteger'},
        {'@name': 'xs:int'},
        {'@name': 'xs:short'},
        {'@name': 'xs:byte'},
        {'@name': 'xs:nonNegativeInteger'},
        {'@name': 'xs:unsignedLong'},
        {'@name': 'xs:positiveInteger'},
        {'@name': 'xs:unsignedInt'},
        {'@name': 'xs:unsignedShort'},
        {'@name': 'xs:unsignedByte'},
        {'@name': 'xs:double'},
        {'@name': 'xs:anyURI'},
        {'@name': 'xs:QName'},
       {'@name': 'xs:NOTATION'},
]
def extract_paths(tree, search_val, path_offset, filter_offset=None, filter_value=None):
    if filter_offset is not None and filter_value is not None:
        extract = [(tuple(k['path'][:path_offset]), k['value']) for k in key_scan_obj(tree, search_val) if k['path'][filter_offset].lower()==filter_value]
    else:
        extract = [(tuple(k['path'][:path_offset]), k['value']) for k in key_scan_obj(tree, search_val) ]
    return extract


def parse_xsd(xsd_bytes):
    xsd_d = xmltodict.parse(xsd_bytes)
    xsd_d['xs:schema']['xs:primitiveType']=prims
    raw_names_d = dict(extract_paths(xsd_d['xs:schema'], "@name", -1))
    raw_bases_d = dict(extract_paths(xsd_d['xs:schema'], "@base", -2, -2, 'xs:restriction') + extract_paths(xsd_d['xs:schema'], "@base", -3, -2, 'xs:extension'))
    raw_types_d = dict(extract_paths(xsd_d['xs:schema'], "@type", -1))
    raw_primitives_d = dict(extract_paths(xsd_d['xs:schema'], "@base", -1, 0, 'xs:primitiveType'))
    raw_primitives_labels_d = {k:"_terminal_" for k,v in raw_primitives_d.items()}

    refs_d = dict([(k,v) for k,v in raw_names_d.items() if not any([p in ['xs:element','xs:attribute'] for p in k[-2:]])])

    # This contains all the specifications required to build the model, keys, (names, types, contextual_clues) TBD: Cardinalities
    specification_d = {k:(v,
                      raw_types_d.get(k, raw_bases_d.get(k,raw_primitives_labels_d.get(k,"_container_"))),
                      "_ref_" if k in refs_d.keys() else "_spec_") for k,v in raw_names_d.items()}

    ref_keys = {v[0]:(k,v[1],v[2]) for k,v in specification_d.items() if v[2]=='_ref_'}
    return raw_names_d, raw_bases_d, raw_types_d, raw_primitives_d, raw_primitives_labels_d, ref_keys, specification_d


def build_(root, spec_d, obj=None):
    ref_keys = {v[0]:(k,v[1],v[2]) for k,v in spec_d.items() if v[2]=='_ref_'}
    if obj is None:
        obj={}
    name, v_type, clue = spec_d.get(root)
    #print(root, name, v_type, clue)
    #print()
    content=[]
    if clue == '_ref_':
        #print("R")
        if v_type == "_container_":
            #print("C")
            for k in spec_d.keys():
                if k[0:len(root)]==root and k!=root:
                    content.append(build_(k, spec_d))
        elif v_type != "_container_" and v_type != "_terminal_":
            #print("!", v_type, clue)
            lookahead = ref_keys.get(v_type)
            if lookahead[1] == "_terminal_":
                content={v_type:{}}
            else:
                content=build_( lookahead[0], spec_d)
        else:
            content=name
    elif clue == '_spec_':

        #print (name, v_type, ref_keys.get(v_type))
        content=build_( ref_keys.get(v_type)[0], spec_d)

    else:
        assert False
        return name, v_type, clue
    obj[name]=content
    return obj
