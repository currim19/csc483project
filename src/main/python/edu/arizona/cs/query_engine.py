from src.main.python.edu.arizona.cs.document import Document
import lucene
from org.apache.lucene import analysis, document, index, queryparser, search, store
from org.apache.lucene.analysis.en import EnglishAnalyzer, PorterStemFilter, KStemFilter
from org.apache.lucene.search.similarities import ClassicSimilarity
from lupyne import engine
lucene.initVM()
# References: http://lupyne.surge.sh/# and http://lupyne.surge.sh/examples.html


def read_txt_file(input_file):
    # add your code here
    file_with_docs = open(input_file, "r")
    doc_title_text = []
    for document in file_with_docs:
        # split each line into array {docID, documentText}, we assume docID is the title
        split_token = " "
        title_text = document.split(split_token, 1)  # we want only 1 split
        # print("Doc: ", title_text[0], " Text: ", title_text[1])
        doc_title_text.append([title_text[0], title_text[1]])
    # docs = None
    # return docs
    return doc_title_text


def pl_build_index(data_file):
    analyzer = analysis.standard.StandardAnalyzer()
    # analyzer = EnglishAnalyzer(Version.LUCENE_CURRENT)
    directory = store.RAMDirectory()
    config = index.IndexWriterConfig(analyzer)
    config.setSimilarity(ClassicSimilarity())  # seems to have no effect on the results
    i_writer = index.IndexWriter(directory, config)
    # print("building index - pylucene God willing")
    doc_title_text = read_txt_file(data_file)
    for dtt in doc_title_text:
        # self.indexer.add(title=doc[0], text=doc[1])
        curr_title = dtt[0]
        curr_text = dtt[1]
        doc = document.Document()
        doc.add(document.Field('text', curr_text, document.TextField.TYPE_STORED))
        doc.add(document.Field('title', curr_title, document.StringField.TYPE_STORED))
        i_writer.addDocument(doc)
    i_writer.close()
    return directory


def pl_search_index(directory, query_text, similarity=None):
    analyzer = analysis.standard.StandardAnalyzer()
    # get to the index
    i_reader = index.DirectoryReader.open(directory)
    i_searcher = search.IndexSearcher(i_reader)
    # adapted from https://stackoverflow.com/questions/43831880/pylucene-how-to-use-bm25-similarity-instead-of-tf-idf
    #  and https://stackoverflow.com/questions/39182236/how-to-rank-documents-using-tfidf-similairty-in-lucene
    if similarity == 'TFIDFSimilarity':
        i_searcher.setSimilarity(ClassicSimilarity())
    # parse the query
    parser = queryparser.classic.QueryParser('text', analyzer)  # our field is called text
    query = parser.parse(query_text)
    hits = i_searcher.search(query, 10).scoreDocs
    ans = []
    for hit in hits:
        # print('hit data', hit)
        hit_doc = i_searcher.doc(hit.doc)
        # print(hit_doc['title'], hit.score)
        answer = Document(hit_doc['title'], hit.score)
        ans.append(answer)
    i_reader.close()
    directory.close()
    return ans


class QueryEngine:

    # def __init__(self):
    def __init__(self, input_file):
        # add your code here
        self.input_file = input_file
        # Indexer combines Writer and Searcher; RAMDirectory and StandardAnalyzer are defaults
        # self.indexer = engine.Indexer()
        self.indexer = self.set_indexer()
        self.build_index(input_file)
        pass

    @staticmethod
    def set_indexer():
        my_index = engine.Indexer()
        # my_index = engine.indexers.Indexer(directory=None, mode='a', analyzer='EnglishAnalyzer')
        return my_index

    def build_index(self, data_file):
        self.indexer.set('title', engine.Field.String, stored=True)
        self.indexer.set('text', engine.Field.Text, stored=True)  # default indexed text settings for documents
        # Get text file, index it
        # print("building index")
        doc_title_text = read_txt_file(data_file)
        for doc in doc_title_text:
            self.indexer.add(title=doc[0], text=doc[1])
        self.indexer.commit()

    # def run_query_lupyne(self, lupyne_query):
    #     hits = self.indexer.search(lupyne_query)
    #     # print("hits details: ", len(hits), hits.count)
    #     ans = []
    #     for hit in hits:
    #         # print(hit.id, hit.score, hit['title'])
    #         answer = Document(hit['title'], hit.score)
    #         ans.append(answer)
    #     return ans

    def run_query(self, my_query):
        hits = self.indexer.search(my_query, field='text')
        # print("hits details: ", len(hits), hits.count)
        ans = []
        for hit in hits:
            # print(hit.id, hit.score, hit['title'])
            answer = Document(hit['title'], hit.score)
            ans.append(answer)
        return ans

    # def q1_1_luc(self, query, similarity=None):
    #     search_directory = pl_build_index(self.input_file)
    #     my_query = ' '.join(query)
    #     sim = None
    #     if similarity == 'TFIDFSimilarity':
    #         sim = similarity
    #     ans = pl_search_index(search_directory, my_query, sim)
    #     # for hit in search_hits:
    #     #     print(hit.doc, hit.score)
    #     return ans

    def q1_1(self, query):
        # This is just sample code. add your actual code here.
        # The Document class we provided is just a dummy wrapper over Lucene document.
        # the document you use must be the Lucene document i.e
        # doc = document.Document()

        # Query (input) is an array of terms. Must be converted to a string (space separated)
        my_query = ' '.join(query)
        # Q = engine.Query
        # Q.term('text', query[0])
        # print("in Q1 query: ", my_query)

        # search for query terms in index
        # hits = self.indexer.search(my_query, field='text')
        # print("hits details: ", len(hits), hits.count)
        # ans = []
        # for hit in hits:
        #     # print(hit.id, hit.score, hit['title'])
        #     answer = Document(hit['title'], hit.score)
        #     ans.append(answer)
        ans = self.run_query(my_query)
        # ans = self.run_query_lupyne(Q)
        # first argument must be of type document.Document()
        # ans1 = Document("Doc1", 1.10)
        # ans2 = Document("Doc1", 1.14)
        # ans.append(ans1)
        # ans.append(ans2)
        return ans

    def q1_2_a(self, query):
        # This is just sample code. add your actual code here.
        # The Document class we provided is just a dummy wrapper over Lucene document.
        # the document you use must be the Lucene document i.e
        # doc = document.Document()

        # query: list of terms, must search using boolean AND
        my_query = ' AND '.join(query)
        # print("in Q2a query: ", my_query)

        # search for query terms in index
        # hits = self.indexer.search(my_query, field='text')
        #
        # ans = []
        # first argument must be of type document.Document()
        # ans1 = Document("Doc2", 1.30)
        # ans2 = Document("Doc2", 1.24)
        # ans.append(ans1)
        # ans.append(ans2)
        # for hit in hits:
        #     # print(hit.id, hit.score, hit['title'])
        #     answer = Document(hit['title'], hit.score)
        #     ans.append(answer)
        ans = self.run_query(my_query)
        return ans

    def q1_2_b(self, query):
        # This is just sample code. add your actual code here.
        # The Document class we provided is just a dummy wrapper over Lucene document.
        # the document you use must be the Lucene document i.e
        # doc = document.Document()
        # ans = []
        # first argument must be of type document.Document()
        # ans1 = Document("Doc2", 1.30)
        # ans.append(ans1)
        my_query = ' AND NOT '.join(query)
        # print("in Q2b query: ", my_query)
        ans = self.run_query(my_query)
        # print('ans len', len(ans))
        return ans

    def q1_2_c(self, query):
        # This is just sample code. add your actual code here.
        # The Document class we provided is just a dummy wrapper over Lucene document.
        # the document you use must be the Lucene document i.e
        # doc = document.Document()
        # ans = []
        # first argument must be of type document.Document()
        # ans1 = Document("Doc2", 1.30)
        # ans.append(ans1)
        my_query = ' '.join(query)
        my_query = '"' + my_query + '"' + '~1'
        # print("in Q2c query: ", my_query)
        ans = self.run_query(my_query)
        return ans

    def q1_3(self, query):
        # This is just sample code. add your actual code here.
        # The Document class we provided is just a dummy wrapper over Lucene document.
        # the document you use must be the Lucene document i.e
        # doc = document.Document()
        ans = []
        # first argument must be of type document.Document()
        # ans1 = Document("Doc3", 1.30)
        # ans2 = Document("Doc2", 1.24)
        # ans.append(ans1)
        # ans.append(ans2)
        search_directory = pl_build_index(self.input_file)
        my_query = ' '.join(query)
        # sim = None
        # if similarity == 'TFIDFSimilarity':
        #     sim = similarity
        sim = 'TFIDFSimilarity'
        ans = pl_search_index(search_directory, my_query, sim)
        return ans


# def main():
#     # can comment this out later
#     # query = "Test"
#     # query = "information retrieval"
#     input_path = "src/main/resources/input2.txt"
#     query = ["information", "retrieval"]  # standard for all questions
#
#     ans1 = QueryEngine(input_path).q1_1(query)
#     # for a in ans1:
#     #     print("Q1_1 docid, score: ", a.get("doc_id"), a.get("score"))
#
#     ans2_a = QueryEngine(input_path).q1_2_a(query)
#     # for a in ans2_a:
#     #     print("Q1_2a docid, score: ", a.get("doc_id"), a.get("score"))
#
#     ans2_b = QueryEngine(input_path).q1_2_b(query)
#     # for a in ans2_b:
#     #     print("Q1_2b docid, score: ", a.get("doc_id"), a.get("score"))
#
#     ans2_c = QueryEngine(input_path).q1_2_c(query)
#     # for a in ans2_c:
#     #     print("Q1_2c docid, score: ", a.get("doc_id"), a.get("score"))
#
#     # # ans1_1_test = QueryEngine(input_path).q1_1_luc(query)
#     # ans1_alt = QueryEngine(input_path).q1_1_luc(query)
#     # for a in ans1_alt:
#     #     print("Q1_1-alt docid, score: ", a.get("doc_id"), a.get("score"))
#     # ans3 = QueryEngine(input_path).q1_3(query, 'TFIDFSimilarity')
#     ans3 = QueryEngine(input_path).q1_3(query)
#     # for a in ans3:
#     #     print("Q3 docid, score: ", a.get("doc_id"), a.get("score"))


# if __name__ == "__main__":
#     main()
