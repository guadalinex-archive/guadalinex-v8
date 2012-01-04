#!/usr/bin/python

import os
import sys
import xapian

try:
    from AppCenter.enums import *
except ImportError:
    # support running from the dir too
    d = os.path.dirname(os.path.abspath(os.path.join(os.getcwd(),__file__)))
    sys.path.insert(0, os.path.split(d)[0])
    from AppCenter.enums import *

if __name__ == "__main__":

    search_term = sys.argv[1]

    xapian_base_path = "/var/cache/software-center"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = xapian.Database(pathname)

    parser = xapian.QueryParser()
    #parser.set_stemmer(xapian.Stem("english"))
    #parser.set_stemming_strategy(xapian.QueryParser.STEM_ALL)
    parser.set_database(db)
    #parser.add_prefix("pkg", "AP")
    query = parser.parse_query(search_term, 
                               xapian.QueryParser.FLAG_PARTIAL|
                               xapian.QueryParser.FLAG_WILDCARD)

    enquire = xapian.Enquire(db)
    enquire.set_sort_by_value_then_relevance(XAPIAN_VALUE_POPCON)
    enquire.set_query(query)
    matches = enquire.get_mset(0, db.get_doccount())
    print "Matches:"
    for m in matches:
        doc = m.document
        popcon = doc.get_value(XAPIAN_VALUE_POPCON)
        print doc.get_data(), "popcon:", xapian.sortable_unserialise(popcon)
        #for t in doc.termlist():
        #    print "'%s': %s (%s); " % (t.term, t.wdf, t.termfreq),
        #print "\n"
        appname = doc.get_data()
    
    # calculate a eset
    print "ESet:"
    rset = xapian.RSet()
    for m in matches:
        rset.add_document(m[xapian.MSET_DID])
    for m in enquire.get_eset(10, rset):
        print m.term


    # calulate the expansions
    completions = []
    for i, m in enumerate(db.allterms(search_term)):
        completions.append("AP"+m.term)
        completions.append(m.term)
        if i > 10:
            break
    expansion = xapian.Query(xapian.Query.OP_OR, completions)
    enquire.set_query(xapian.Query(xapian.Query.OP_OR, query, expansion))
    matches = enquire.get_mset(0, 10)
    print "\n\nExpanded Matches:"
    for m in matches:
        doc = m.document
        print doc.get_data()
        appname = doc.get_data()
    
    
    # popular
    print
    print "Popular: "
    query = xapian.Query(xapian.Query.OP_VALUE_GE,
                         XAPIAN_VALUE_POPCON, "100000")
    enquire.set_query(query)
    matches = enquire.get_mset(0, 10)
    for m in matches:
        doc = m.document
        print doc.get_data()
        appname = doc.get_data()
    
