# you should change this document class to use: from org.apache.lucene import  document
import lucene
from org.apache.lucene import document


# from lucene import analysis, document, index, queryparser, search, store
# from org.apache.lucene import analysis, document, index, queryparser, search, store


class Document:
    def __init__(self, doc_id, score):
        # first argument must be of type document.Document() and you should get docid using doc.get("docid")
        self.doc_id = doc_id
        self.score = score

    def get(self, attribute):
        if attribute == "doc_id" or attribute == "docid":
            return self.doc_id
        if attribute == "score":
            return self.score
