# from src.main.python.edu.arizona.cs.document import Document
from operator import itemgetter
import glob
import re
import spacy
import time
import json

# import numpy as np
import lucene
from java.nio.file import Paths
from org.apache.lucene import analysis, document, index, queryparser, search, store
from org.apache.lucene.analysis.en import EnglishAnalyzer, PorterStemFilter, KStemFilter
from org.apache.lucene.search.similarities import ClassicSimilarity
from org.apache.lucene.store import SimpleFSDirectory
from lupyne import engine
lucene.initVM()

DEFAULT_INDEX_DIRECTORY = "my_index"
DEFAULT_INDEX_DIRECTORY_CATS = "c_index"
SHORT_INDEX_CATS_2K = "index2k"
SHORT_INDEX_CATS_4K = "index4k"
ENG_INDEX_DIRECTORY = "stem_index"
SHORT_INDEX_LEMMA_OLD = "cut_index"
SHORT_INDEX_LEMMA = "s_index"
LONG_INDEX_LEMMA = "l_index"
ENG_SHORT_INDEX_LEMMA = "es_index"
ENG_LONG_INDEX_LEMMA = "el_index"
ENG_STOP_NO_LEMMA = "e_stop"
ENG_STOP_NO_LEMMA_TF = "e_stop_tf"
ENG_STOP_NO_LEMMA_4K = "e_stop_4k"
LEMMA_4K = "lemma4k"
LEMMA_FULL = "lemma_full"  # uses spacy's longer stop word list
MAX_DOC_LENGTH = 4000
OVERLAP_ARRAY = []

# References: http://lupyne.surge.sh/# and http://lupyne.surge.sh/examples.html


def read_questions_file(input_file):
    category_question_answer = []
    curr_category = None
    curr_question = None
    curr_answer = None
    # file_lines = open(input_file, "r", encoding='utf-8')
    with open(input_file, "r", encoding='utf-8') as file_lines:
        for line in file_lines:
            clean_line = line.strip()
            if len(clean_line) == 0:  # empty
                continue
            else:  # lines appear in sequence, category -> question -> answer
                if curr_category is None:
                    curr_category = clean_line
                elif curr_question is None:
                    curr_question = clean_line
                else:
                    curr_answer = clean_line
                    # add item to array
                    category_question_answer.append([curr_category, curr_question, curr_answer])
                    curr_category = None
                    curr_question = None
                    curr_answer = None
    return category_question_answer


def text_replace_none(categories):
    my_cat = categories
    if my_cat is None:
        my_cat = ""
    else:
        my_cat = my_cat.strip().lstrip(', ')
    return my_cat


def remove_tpl(input_string):  # remove tpl, redirect tag
    return re.sub(r"\[tpl\](.*)\[/tpl\]", "", input_string.lstrip("#REDIRECT "))


def remove_stop_words(input_string, custom_word_list=None):  # remove stop words using lucene stop word list
    if custom_word_list is None:
        stop_words = ["a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "if", "in", "into", "is", "it", "no",
                  "not", "of", "on", "or", "such", "that", "the", "their", "then", "there", "these", "they", "this",
                  "to", "was", "will", "with"]
    else:
        stop_words = custom_word_list
    result_no_stop = []
    # modification of https://stackoverflow.com/questions/17527741/what-is-the-default-list-of-stopwords-used-in-lucenes-stopfilter
    # also https://medium.com/@makcedward/nlp-pipeline-stop-words-part-5-d6770df8a936
    input_list = input_string.split()
    for word in input_list:
        if word not in stop_words:
            result_no_stop.append(word)
    result_string = ' '.join(result_no_stop)
    return result_string


def contains_stop_word(input_string, stop_word_string):
    contains_word = False
    my_input_string = input_string.lower().replace("-", " ")
    my_stop_word_string = stop_word_string.lower().replace("-", " ")
    my_stop_word_list = my_stop_word_string.lower().split()
    my_input_list = my_input_string.split()
    for word in my_stop_word_list:
        if word in my_input_list:
            contains_word = True
            overlap_string = "Answer: " + my_input_string + "| Question: " + my_stop_word_string
            # print('Overlap: ', overlap_string)
            OVERLAP_ARRAY.append(overlap_string)
            break
    return contains_word


def doc_process(doc_title, doc_text, doc_length_limit, categories, headings):
    clean_categories = text_replace_none(categories)
    clean_headings = text_replace_none(headings)
    # current_document = remove_tpl(doc_text)
    # remove tpl- gets rid of refs
    # safe even if length < limit https://stackoverflow.com/questions/3486384/output-first-100-characters-in-a-string
    # if isinstance(doc_length_limit, int) and len(doc_text) > doc_length_limit:
    if isinstance(doc_length_limit, int):
        # print("Len from -> to", len(doc_text), length_limit)
        extra_len = doc_length_limit + 500
        current_document = doc_text[0:extra_len]  # extra for tpl cleaning
    else:
        current_document = doc_text
    # remove [tpl], then fast lemma
    # current_document = fast_lemma(remove_tpl(current_document))
    current_document = remove_tpl(current_document)
    current_document = remove_stop_words(current_document)
    # add categories at the end
    current_document += ' ' + text_replace_none(clean_categories)
    #  docs_title_cat_text_head.append([curr_title, text_replace_none(curr_categories), current_document, text_replace_none(curr_headings)])
    processed_list = [doc_title, clean_categories, current_document, clean_headings]
    return processed_list


def read_txt_file(input_file, max_doc_len=None):
    # add your code here
    # file_lines = open(input_file, "r", encoding='utf-8')
    with open(input_file, "r", encoding='utf-8') as file_lines:
        docs_title_cat_text_head = []
        current_document = ""
        curr_title = None
        curr_categories = []
        curr_headings = ""
        check_heading_string_pos = 0  # check_heading() returns: line + true/false
        check_heading_is_head_pos = 1
        i = 0
        is_new_doc = False
        is_line_after_cat = False
        at_references = False
        for line in file_lines:
            # check if title
            get_title = check_is_title(line)
            # if i % 1000 == 0:  # print every 1000th line
            #     print(line)
            if get_title is not None:  # some title returned
                if curr_title is not None:  # new article (not first line)
                    i += 1
                    # if i % 1000 == 0:  # every 1000th article
                    #     # print("Title: ", curr_title, "Categories: ", curr_categories, "Doc Text: ", current_document)
                    #     print("Title: ", curr_title)
                    # if isinstance(max_doc_len, int) and len(current_document) > max_doc_len:
                    #     # print("Len from -> to", len(current_document), max_doc_len)
                    #     current_document = current_document[0:max_doc_len]
                    # # add categories at the end
                    # current_document += ' ' + text_replace_none(curr_categories)
                    proc_doc_list = doc_process(curr_title, current_document, max_doc_len, curr_categories,
                                                curr_headings)
                    # docs_title_cat_text_head.append([curr_title, text_replace_none(curr_categories), current_document, text_replace_none(curr_headings)])
                    docs_title_cat_text_head.append(proc_doc_list)
                    # for new article
                    curr_title = get_title
                    current_document = ""  # reset to new string for new article
                    curr_headings = ""  # reset to new string for new article
                    is_new_doc = True
                    pass
                else:  # first line
                    # curr_title = line
                    curr_title = get_title
                    is_new_doc = True
                    pass
            else:  # non-title line
                if is_new_doc:
                    at_references = False  # new doc, no longer at the "end of old doc"
                    strip_line = line.strip()  # get rid of blank space at top of new document
                    if len(strip_line) > 0:  # has content
                        # check if categories line
                        curr_categories = check_is_categories(line)  # string or none
                        # otherwise this article may not have categories
                        if curr_categories is None:  # it's a regular line
                            heading_check_line = check_heading(line)
                            current_document += heading_check_line[check_heading_string_pos]
                            if heading_check_line[check_heading_is_head_pos]:  # is true
                                curr_headings += ", " + heading_check_line[check_heading_string_pos]
                        else:
                            is_line_after_cat = True
                            pass  # is a category, but we do nothing else because it's already in "curr_categories"
                        is_new_doc = False  # has content - no longer new doc
                    else:  # no content
                        pass
                else:  # not a new doc
                    if is_line_after_cat:  # skip blank line after categories
                        strip_line = line.strip()
                        if len(strip_line) > 0:  # has content
                            is_line_after_cat = False
                            heading_check_line = check_heading(line)
                            current_document += heading_check_line[check_heading_string_pos]
                            if heading_check_line[check_heading_is_head_pos]:  # is true
                                curr_headings += ", " + heading_check_line[check_heading_string_pos]
                        else:  # empty line, skip it
                            continue
                    else:  # not the line after categories
                        if at_references:
                            continue  # don't include this line, reset this once you find a new document
                        else:  # need to examine the line
                            at_references = check_start_references(line)
                            if not at_references:  # include the line
                                heading_check_line = check_heading(line)
                                current_document += heading_check_line[check_heading_string_pos]
                                if heading_check_line[check_heading_is_head_pos]:  # is true
                                    curr_headings += ", " + heading_check_line[check_heading_string_pos]
            # i += 1
            # if i > 200:
            #     break
        # docs = None
        # return docs
        # This is the last document - since the "new title" catch won't find it
        # if isinstance(max_doc_len, int) and len(current_document) > max_doc_len:
        #     current_document = current_document[0:max_doc_len]
        # # add categories at the end
        # current_document += ' ' +text_replace_none(curr_categories)
        # docs_title_cat_text_head.append([curr_title, text_replace_none(curr_categories), current_document, text_replace_none(curr_headings)])
        proc_doc_list = doc_process(curr_title, current_document, max_doc_len, curr_categories, curr_headings)
        docs_title_cat_text_head.append(proc_doc_list)
    return docs_title_cat_text_head


def check_is_title(line):
    # returns None if not a title
    title = None
    strip_line = line.strip()
    title_prefix = "[["
    title_suffix = "]]"
    line_begin = strip_line[0:2]
    line_end = strip_line[-2:]  # https://stackoverflow.com/questions/59036609/python-get-last-2-characters-of-a-string
    # print("strip line: ", strip_line, " begin: ", line_begin, "; end: ", line_end)
    if (line_begin == title_prefix) and (line_end == title_suffix):
        title = strip_line[2:-2]  # remove the [[ and ]]
    return title


def check_heading(line):
    # returns [line, True/False] 
    result = [line, False]
    heading_prefix = "=="
    heading_suffix = "=="
    strip_line = line.strip()
    if len(strip_line) > (len(heading_prefix) + len(heading_suffix)):  # a possibility
        line_begin = strip_line[0:2]
        line_end = strip_line[-2:]
        # print("strip line: ", strip_line, " begin: ", line_begin, "; end: ", line_end)
        if (line_begin == heading_prefix) and (line_end == heading_suffix):
            # heading = strip_line[2:-2]  # remove the == and == at begin and end and any trailing space
            heading = strip_line.strip("=")
            result = [heading, True]
    return result


def check_is_categories(line):
    # is_category = False
    # note we return None if no categories, otherwise we return categories God willing
    to_return = None
    # categories = []
    strip_line = line.strip()
    cat_prefix = "CATEGORIES: "
    cat_len_prefix = len(cat_prefix)
    if len(strip_line) > cat_len_prefix:  # could possible have categories
        line_begin = strip_line[0:cat_len_prefix]
        if line_begin == cat_prefix:
            # is_category = True
            cat_string = strip_line[cat_len_prefix:]  # get substring starting after the "CATEGORIES: "
            # categories = cat_string.split(", ") # returns array -- but we want it a string
            # ######### following may be useful ? ###########
            # cat_string = cat_string.lower()  # make it lower case (to help with search, God willing)
            # cat_string = cat_string.replace(", ", " ")
            # cat_string = cat_string.replace("  ", " ")
            cat_string = cat_string.strip()
            categories = cat_string
            if len(categories) > 0:
                to_return = categories
    # return a string God willing (if data) or None
    return to_return


def check_start_references(line):
    to_return = False
    strip_line = line.strip()
    refs_match = "==References=="
    if strip_line == refs_match:
        to_return = True
    return to_return


# index_directory=None, index_mode=None, analyzer=None
# build_index_eng(None, None, data_pre_calc, index_to_use)
# def build_index_eng(data_files, max_doc_len=None, data_pre_calc=None, index_directory=None):
def build_index_eng(data_files_params, data_pre_calc=None, index_directory=None, sim_method=None):
    # analyzer = analysis.standard.StandardAnalyzer()
    # analyzer = EnglishAnalyzer(Version.LUCENE_CURRENT)
    if (data_files_params is None) and (data_pre_calc is None):
        return "Error: must specify either data_files_params or data_pre_calc"
    # doc_t_c_t_h_list = []
    if data_pre_calc is None:  # need to process text files
        file_list_index = 0
        doc_len_index = 1
        data_files = data_files_params[file_list_index]
        max_doc_len = data_files_params[doc_len_index]
        doc_t_c_t_h_list = get_data_from_txt_files(data_files, max_doc_len)
    else:
        doc_t_c_t_h_list = read_json_list_dump(data_pre_calc)

    # directory = None means RAMDirectory()
    if index_directory is None:
        directory = store.RAMDirectory()
    else:
        directory = SimpleFSDirectory.open(Paths.get(index_directory))
    analyzer = EnglishAnalyzer(EnglishAnalyzer.ENGLISH_STOP_WORDS_SET)
    config = index.IndexWriterConfig(analyzer)
    if sim_method == "tfidf":
        config.setSimilarity(ClassicSimilarity())  # seems to have no effect on the results
    # config.setOpenMode(index_mode)  - default is create / new
    i_writer = index.IndexWriter(directory, config)
    print("building index God willing, english analyzer, with index_directory: ", index_directory)
    doc_counter = 0
    title_index = 0
    category_index = 1
    text_index = 2
    heading_index = 3
    # i = 0
    for doc in doc_t_c_t_h_list:
        # self.indexer.add(title=doc[0], text=doc[1])
        curr_title = doc[title_index]
        curr_categories = doc[category_index]
        # curr_text = ''.join(doc[text_index]).lstrip("#REDIRECT ")  # seems to be an array for some reason / removed with tpl
        curr_text = ''.join(doc[text_index])
        curr_headings = doc[heading_index]
        # print(curr_title, '|', curr_categories, '|', curr_headings)
        # print(curr_text)
        # i += 1
        # if i >= 2:
        #     break
        doc = document.Document()
        doc.add(document.Field('text', curr_text, document.TextField.TYPE_STORED))
        doc.add(document.Field('title', curr_title, document.TextField.TYPE_STORED))
        doc.add(document.Field('categories', curr_categories, document.TextField.TYPE_STORED))
        doc.add(document.Field('headings', curr_headings, document.TextField.TYPE_STORED))
        i_writer.addDocument(doc)
        doc_counter += 1
    i_writer.close()
    # return directory
    print("documents indexed God willing: ", doc_counter)
    return doc_counter


# def pl_search_index(directory, query_text, similarity=None):
#     analyzer = analysis.standard.StandardAnalyzer()
#     # get to the index
#     i_reader = index.DirectoryReader.open(directory)
#     i_searcher = search.IndexSearcher(i_reader)
#     # adapted from https://stackoverflow.com/questions/43831880/pylucene-how-to-use-bm25-similarity-instead-of-tf-idf
#     #  and https://stackoverflow.com/questions/39182236/how-to-rank-documents-using-tfidf-similairty-in-lucene
#     if similarity == 'TFIDFSimilarity':
#         i_searcher.setSimilarity(ClassicSimilarity())
#     # parse the query
#     parser = queryparser.classic.QueryParser('text', analyzer)  # our field is called text
#     query = parser.parse(query_text)
#     hits = i_searcher.search(query, 10).scoreDocs
#     ans = []
#     for hit in hits:
#         # print('hit data', hit)
#         hit_doc = i_searcher.doc(hit.doc)
#         # print(hit_doc['title'], hit.score)
#         answer = Document(hit_doc['title'], hit.score)
#         ans.append(answer)
#     i_reader.close()
#     directory.close()
#     return ans


# for new index, assumes default mode = w for write
def new_disk_indexer(directory=None):
    # my_index = engine.Indexer()
    # my_index = engine.indexers.Indexer(directory=None, mode='a', analyzer='EnglishAnalyzer')
    if directory is None:
        my_directory = DEFAULT_INDEX_DIRECTORY  # default directory
    else:
        my_directory = directory
    # since new index - assume default mode is "w"
    my_mode = "w"
    # mode of "w" will create / over write. mode of 'a' will append
    # my_index = engine.indexers.Indexer(directory=my_directory, mode=my_mode)
    # my_index = engine.indexers.Indexer(directory=my_directory, mode=my_mode)
    my_indexer = get_indexer(my_directory, my_mode)
    return my_indexer


def get_indexer(index_directory=None, index_mode=None, analyzer=None):
    # assumes existing index / not one to be over-written, hence mode of "a" by default
    # default_mode = "a"
    # note: index_directory of "None" means RamDirectory
    # my_index = engine.indexers.Indexer(directory=None, mode='a')
    # my_index = engine.indexers.Indexer()
    my_mode = "a"
    if index_mode is not None:
        my_mode = index_mode
    my_analyzer = None
    if analyzer is not None:
        my_analyzer = analyzer
    # my_indexer = engine.indexers.Indexer(directory=index_directory, mode=my_mode)
    my_indexer = engine.indexers.Indexer(directory=index_directory, mode=my_mode, analyzer=my_analyzer)
    return my_indexer


# uncomment later God willing
def build_index_std(data_files_params, data_pre_calc=None, index_directory=None, index_mode=None, do_lemma=None):
    if (data_files_params is None) and (data_pre_calc is None):
        return "Error: must specify either data_files_params or data_pre_calc"
    # self.indexer.set('title', engine.Field.String, stored=True)
    # self.indexer.set('text', engine.Field.Text, stored=True)  # default indexed text settings for documents
    if data_pre_calc is None:  # need to process text files
        print("God willing reading raw text files ... ")
        file_list_index = 0
        doc_len_index = 1
        data_files = data_files_params[file_list_index]
        max_doc_len = data_files_params[doc_len_index]
        doc_t_c_t_h_list = get_data_from_txt_files(data_files, max_doc_len)
    else:
        print("God willing reading from file dump: ", data_pre_calc)
        doc_t_c_t_h_list = read_json_list_dump(data_pre_calc)

    # # my_indexer = get_indexer(index_directory, index_mode)
    # if analyzer is not None:
    #     my_analyzer = analyzer
    #     my_indexer = get_indexer(index_directory, index_mode, analyzer=my_analyzer)
    # else:
    my_indexer = get_indexer(index_directory, index_mode)
    print("God willing Calling indexer with no analyzer, directory: ", index_directory, " Mode: ", index_mode)

    my_indexer.set('title', engine.Field.String, stored=True)
    my_indexer.set('text', engine.Field.Text, stored=True)  # default indexed text settings for documents
    my_indexer.set('categories', engine.Field.Text, stored=True)
    my_indexer.set('headings', engine.Field.Text, stored=True)

    print("building index")

    title_index = 0
    category_index = 1
    text_index = 2
    heading_index = 3
    # i = 0
    print("estimated len index: ", len(doc_t_c_t_h_list), " option lemma: ", do_lemma)
    for doc in doc_t_c_t_h_list:
        curr_text = ''.join(doc[text_index]).lstrip("#REDIRECT ")  # seems to be an array
        # i += 1
        # if i == 1 or i == 2 or i == 10 or i == 100 or i % 1000 == 0:
        #     print("God willing, loop: ", i, doc[title_index], ' CAT: ', doc[category_index], " H:", doc[heading_index])
        #     print(curr_text)
        # if i > 2:
        #     break
        if (do_lemma is None) or (not do_lemma):  # takes too long!!
            my_indexer.add(title=doc[title_index], text=curr_text, categories=doc[category_index],
                           headings=doc[heading_index])
        else:
            my_indexer.add(title=doc[title_index], text=fast_lemma(curr_text), categories=doc[category_index],
                           headings=doc[heading_index])
    my_indexer.commit()
    print("Num index entries God willing: ", len(doc_t_c_t_h_list))
    return None


def clean_query(query_string):
    # remove unwanted characters
    my_string = query_string
    # my_string = my_string.replace("\\", " ")
    # my_string = my_string.replace("!", " ")
    # my_string = my_string.replace("&", " ")
    # my_string = my_string.replace("--", " ")
    # my_string = my_string.replace("(", " ")
    # my_string = my_string.replace(")", " ")
    # my_string = my_string.replace("(Alex: ", " ")
    # my_string = my_string.replace("(alex: ", " ")
    # my_string = my_string.replace('"', ' ')
    # my_string = my_string.replace("  ", " ").strip()
    # retain double quotes as they may be useful
    # for chk in ['\\', '!', '&', '--', "(Alex: We'll give you the ", "You give us the ", "You tell us the ",
    #             "(alex: we'll give you the ", 'alex:', ' and ', ' not ', ' or ', '(', ')', ',', ':', '. ', '--',
    #             '   ', '  ']:
    for chk in ['\\', '!', '&', '--', "(Alex: We'll give you the ", "You give us the ", "You tell us the ",
                "(alex: we'll give you the ", 'alex:', ' and ', ' not ', ' or ', '(', ')', '"', ',', ':', '. ', '--',
                '   ', '  ']:
        if chk in my_string:
            my_string = my_string.replace(chk, " ")
    my_string = my_string.strip()
    return my_string


def lemma_pipe(input_doc_list):
    pun_pos = "PUNCT"  # punctuation
    part_pos = "PART"  # particle
    lemmatized_collection = []
    nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])
    ctr = 0
    start_time = time.time()
    for doc in nlp.pipe(input_doc_list):
        ctr += 1
        if ctr % 10000 == 0:
            print(ctr, "loop, elapsed_time: %s", time.time() - start_time)
        doc_lemma_list = []
        for token in doc:
            if not (
                    token.text == '\n' or token.text == '\n\n' or token.text == '\n\n\n' or token.is_stop or token.pos_ == pun_pos or (
                    token.pos_ == part_pos and token.lemma_ == "'s")):
                doc_lemma_list.append(token.lemma_)
        doc_lemma_string = " ".join(doc_lemma_list)
        doc_lemma_string = re.sub(' ,', '', doc_lemma_string)  # remove ', ' cases
        doc_lemma_string = re.sub('  ', ' ', doc_lemma_string)
        lemmatized_collection.append([doc_lemma_string])
    return lemmatized_collection


def fast_lemma(input_string):
    # nlp = spacy.load("en_core_web_sm", disable=["ner", "parser", "tagger"])
    nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])
    query_lemma_list = []
    tokens_data = nlp(input_string)
    # i = 0
    for token in tokens_data:
        # print(token.lemma_, token.pos, token.pos_)
        query_lemma_list.append(token.lemma_)
    query_lemma_string = " ".join(query_lemma_list)

    return query_lemma_string


# def lemmatize_string(query_data, retain_pos_tags=None, token_or_lemma=None, soft_rules=None):
#     # tokenize and lemmatize the query
#     nlp = spacy.load("en_core_web_sm")
#     # query_lemmas = []
#     query_lemma_string = ""
#     query = []
#     pun_pos = "PUNCT"  # punctuation
#     part_pos = "PART"  # particle
#     quote_open = False
#     append_without_space = False
#     # pronoun_pos = "PRON"  # pronoun
#     # assume can get a list of terms, convert to list if string
#     if isinstance(query_data, str):
#         query.append(query_data)
#     if isinstance(query_data, list):
#         query = query_data
#     for q_term in query:
#         # clean_q_term = clean_query(q_term)  # already being done
#         clean_q_term = q_term
#         # print(clean_q_term)
#         tokens_data = nlp(clean_q_term)
#         # merge if compound terms
#         query_lemma = ""
#         i = 0
#         for token in tokens_data:
#             # print(token.lemma_, token.pos, token.pos_)
#             keep_token = False
#             if retain_pos_tags is not None:  # only keep these pos tags
#                 for tag in retain_pos_tags:
#                     if tag == token.pos_:
#                         keep_token = True
#                         break
#             # get rid of some unhelpful parts of speech  anyway
#             # elif token.pos_ == pun_pos or token.pos_ == pronoun_pos or (token.pos_ == part_pos and token.lemma_ == "'s"):
#             elif soft_rules:  # is true
#                 # print("soft rules .. ", token.text, token.lemma_)
#                 if (token.pos_ == pun_pos and token.text != '"') or (token.pos_ == part_pos and token.lemma_ == "'s"):
#                     # print("Skipping: ", token.text)
#                     continue
#                 else:
#                     keep_token = True
#                     if token.text == '"':
#                         quote_open = not quote_open
#             elif token.pos_ == pun_pos or token.is_stop or (token.pos_ == part_pos and token.lemma_ == "'s"):
#                 # print("Skipping: ", token.text)
#                 continue
#             else:
#                 keep_token = True  # don't discard this word / token
#                 # print("keep true ..: ", token.text, token.lemma_)
#             if keep_token:  # is true - dont throw this word away
#                 word_to_keep = token.lemma_
#                 if token_or_lemma == "token":
#                     word_to_keep = token.text
#                 if i == 0:  # first term in string
#                     # query_lemma = token.lemma_
#                     query_lemma = word_to_keep
#                 else:  # second term onwards in string
#                     # query_lemma = query_lemma + ' ' + token.lemma_
#                     if word_to_keep == '"':
#                         if quote_open:
#                             append_without_space = not append_without_space
#                             query_lemma = query_lemma + ' ' + word_to_keep
#                         else:  # quote close
#                             query_lemma = query_lemma + word_to_keep
#                     else:
#                         if append_without_space:
#                             query_lemma = query_lemma + word_to_keep
#                             append_without_space = not append_without_space
#                         else:
#                             query_lemma = query_lemma + ' ' + word_to_keep
#                 i += 1
#         # print("clean query: ", query_lemma)
#         # query_lemmas.append(query_lemma)  # put in list
#         if len(query_lemma) == 0:  # oops, we took out too much
#             if len(tokens_data) > 0:  # non -empty
#                 query_lemma = tokens_data[0].lemma_  # get first token
#                 print("empty lemmas: ", query_data)
#         query_lemma_string += query_lemma
#         # make string
#     # return query_lemmas
#     # print("final doc lem: ", query_lemma_string)
#     return query_lemma_string
# simpler version of the lemmatization
def lemmatize_string(query_data, retain_pos_tags=None, token_or_lemma=None, soft_rules=None):
    # tokenize and lemmatize the query
    nlp = spacy.load("en_core_web_sm")
    # query_lemmas = []
    query_lemma_string = ""
    query = []
    pun_pos = "PUNCT"  # punctuation
    part_pos = "PART"  # particle
    quote_open = False
    append_without_space = False
    # pronoun_pos = "PRON"  # pronoun
    # assume can get a list of terms, convert to list if string
    if isinstance(query_data, str):
        query.append(query_data)
    if isinstance(query_data, list):
        query = query_data
    for q_term in query:
        # clean_q_term = clean_query(q_term)  # already being done
        clean_q_term = q_term
        # print(clean_q_term)
        tokens_data = nlp(clean_q_term)
        # merge if compound terms
        query_lemma = ""
        i = 0
        for token in tokens_data:
            # print(token.lemma_, token.pos, token.pos_)
            keep_token = False
            if retain_pos_tags is not None:  # only keep these pos tags
                for tag in retain_pos_tags:
                    if tag == token.pos_:
                        keep_token = True
                        break
            # get rid of some unhelpful parts of speech  anyway
            # elif token.pos_ == pun_pos or token.pos_ == pronoun_pos or (token.pos_ == part_pos and token.lemma_ == "'s"):
            elif soft_rules:  # is true
                # print("soft rules .. ", token.text, token.lemma_)
                if (token.pos_ == pun_pos) or (token.pos_ == part_pos and token.lemma_ == "'s"):
                    # print("Skipping: ", token.text)
                    continue
                else:
                    keep_token = True
            elif token.pos_ == pun_pos or token.is_stop or (token.pos_ == part_pos and token.lemma_ == "'s"):
                # print("Skipping: ", token.text)
                continue
            else:
                keep_token = True  # don't discard this word / token
                # print("keep true ..: ", token.text, token.lemma_)
            if keep_token:  # is true - dont throw this word away
                word_to_keep = token.lemma_
                if token_or_lemma == "token":
                    word_to_keep = token.text
                if i == 0:  # first term in string
                    # query_lemma = token.lemma_
                    query_lemma = word_to_keep
                else:  # second term onwards in string
                    query_lemma = query_lemma + ' ' + word_to_keep
                i += 1
        # print("clean query: ", query_lemma)
        # query_lemmas.append(query_lemma)  # put in list
        if len(query_lemma) == 0:  # oops, we took out too much
            if len(tokens_data) > 0:  # non -empty
                query_lemma = tokens_data[0].lemma_  # get first token
                print("empty lemmas: ", query_data)
        query_lemma_string += query_lemma
        # make string
    # return query_lemmas
    # print("final doc lem: ", query_lemma_string)
    return query_lemma_string

# https://stackoverflow.com/questions/36217842/python-column-slice-of-list-of-list-matrix
def get_column(list_, n):
    return map(itemgetter(n), list_)


def parse_dump_files(text_file_list, dump_file_name, max_doc_len, do_lemma=None):
    title_index = 0
    category_index = 1
    heading_index = 3
    text_index = 2
    # for curr_file in text_file_list:
    #     doc_t_c_t_h += read_txt_file(curr_file, max_doc_len)
    doc_t_c_t_h = get_data_from_txt_files(text_file_list, max_doc_len)
    # ref: https://stackoverflow.com/questions/27745500/how-to-save-a-list-to-a-file-and-read-it-as-a-list-type
    # with open("file_parsed_json.txt", "w") as fp:
    merged_list = []
    if do_lemma is None:
        merged_list = doc_t_c_t_h
    else:
        docs_list = get_column(doc_t_c_t_h, text_index)
        lemmatized_docs = lemma_pipe(docs_list)
        loop_len = len(doc_t_c_t_h)
        if loop_len == len(lemmatized_docs):
            for counter in range(loop_len):
                merged_list.append(
                    [doc_t_c_t_h[counter][title_index], doc_t_c_t_h[counter][category_index], lemmatized_docs[counter],
                     doc_t_c_t_h[counter][heading_index]])
        else:
            print("mismatched list sizes.. something is wrong")

    # with open(dump_file_name, "w") as fp:
    #     json.dump(merged_list, fp)
    write_list_to_json(dump_file_name, merged_list)


def write_list_to_json(dump_file_name, list_to_dump):
    with open(dump_file_name, "w") as fp:
        json.dump(list_to_dump, fp)


def read_json_list_dump(dump_file_name):
    doc_title_cat_txt_head_list = []
    with open(dump_file_name, "r") as fp:
        doc_title_cat_txt_head_list = json.load(fp)
        print("Praise God, reading json: ", len(doc_title_cat_txt_head_list))
        # ctr = 0
        # for line in fp:
        #     doc_title_cat_txt_head_list.append(line.strip())
        #     ctr += 1
        #     if ctr == 1 or ctr == 100 or ctr == 1000  or ctr == 10000 or ctr == 50000 or ctr == 100000:
        #         print("Praise God, reading ctr: ", ctr)
    return doc_title_cat_txt_head_list


def get_data_from_txt_files(txt_file_list, max_doc_len):
    my_data_files = []
    doc_t_c_t_h_list = []
    if isinstance(txt_file_list, str):
        my_data_files.append(txt_file_list)  # make it a list of one entry
        # print(type(my_data_files))
    else:
        my_data_files = txt_file_list
    for curr_file in my_data_files:
        doc_t_c_t_h_list += read_txt_file(curr_file, max_doc_len)
        print("God willing processed: ", curr_file)
    return doc_t_c_t_h_list


class QueryEngine:

    def __init__(self, provided_index_directory):
        # add your code here
        self.curr_index_dir = provided_index_directory
        # Indexer combines Writer and Searcher; RAMDirectory and StandardAnalyzer are defaults
        # self.indexer = engine.Indexer()
        # self.indexer = self.set_indexer()  # uncomment later God willing
        # self.build_index(input_files)  # uncomment later God willing
        pass

    # uncomment later God willing
    def run_query(self, query_text, similarity_method, stem=None, search_limit=None):
        if search_limit is None:
            search_limit_count = 1
        else:
            search_limit_count = search_limit
        field_to_search = 'text'
        if (similarity_method == "bm25") and (stem is None):
            hits = self.get_hits_bm25(query_text, search_limit_count, field_to_search)
        elif (similarity_method == "tfidf") or (stem == "English"):
            hits = self.get_hits_flex(query_text, search_limit_count, field_to_search, sim=similarity_method,
                                      stem="English")
        # elif similarity_method == "tfidf" and (stem == "English"):
        #     hits = self.get_hits_flex(query_text, search_limit_count, field_to_search)
        else:
            hits = None
            print("Unknown Search method .. please use tfidf or bm25")
        max_results = search_limit
        loop_len = min(max_results, len(hits))
        ans = []
        # for hit in hits:
        for counter in range(loop_len):
            # print(hit.id, hit.score, hit['title'])
            # answer = Document(hit['title'], hit.score)
            # answer = Document(hits[counter]['title'], hits[counter].score)
            answer = [hits[counter][0], hits[counter][1]]
            ans.append(answer)
        return ans

    def run_query_get_doc(self, query_text, similarity_method, num_results=None, stem=None):
        if num_results is None:
            search_limit_count = 1
        else:
            search_limit_count = num_results
        if stem is None:
            my_stem = None
        else:
            my_stem = "English"
        field_to_search = 'text'
        # print(query_text)
        hits = self.get_hits_flex(query_text, search_limit_count, field_to_search, sim=similarity_method, stem=my_stem)
        ans = []
        # print(hit.id, hit.score, hit['title'])
        # answer = Document(hit['title'], hit.score)
        # answer = Document(hits[counter]['title'], hits[counter].score)
        # answer = [hits[0][0], hits[0][1], hits[0][2]]
        # ans.append(answer)
        loop_len = min(search_limit_count, len(hits))
        ans = []
        # for hit in hits:
        for counter in range(loop_len):
            # print(hit.id, hit.score, hit['title'])
            # answer = Document(hit['title'], hit.score)
            # answer = Document(hits[counter]['title'], hits[counter].score)
            answer = [hits[counter][0], hits[counter][1]]
            ans.append(answer)
        return ans

    def get_hits_bm25(self, query_text, search_limit_count, field_to_search, stem=None):
        # if isinstance(lemma_query, list):  # convert list to string
        #     my_query = ' '.join(lemma_query)
        # else:
        #     my_query = lemma_query
        # lemma query returns  a string
        # lemma_query = lemmatize_string(query_text)  # done before
        my_query = query_text
        if stem == "English":
            my_indexer = get_indexer(self.curr_index_dir, analyzer=EnglishAnalyzer)
        else:
            my_indexer = get_indexer(self.curr_index_dir)
        hits = my_indexer.search(my_query, count=search_limit_count, field=field_to_search)
        ans = []
        for hit in hits:
            # answer = Document(hit['title'], hit.score)
            answer = [hit['title'], hit.score]
            ans.append(answer)
        # print("hits details: ", len(hits), hits.count)
        return ans

    def get_hits_flex(self, query_text, search_limit_count, field_to_search, sim=None, stem=None):
        # hits = self.get_hits_flex(query_text, search_limit_count, field_to_search, sim=similarity_method, stem="English")
        # print("flex God willing: ", sim, stem, query_text)
        if stem is None:
            analyzer = analysis.standard.StandardAnalyzer()
        else:
            analyzer = EnglishAnalyzer()
        # get to the index
        # directory = SimpleFSDirectory.open(Paths.get(INDEX_DIR))
        # directory = store.SimpleFSDirectory(self.curr_index_dir)
        directory = SimpleFSDirectory.open(Paths.get(self.curr_index_dir))
        i_reader = index.DirectoryReader.open(directory)
        i_searcher = search.IndexSearcher(i_reader)
        if sim == "tfidf":  # otherwise default is fine - BM25
            i_searcher.setSimilarity(ClassicSimilarity())
        # adapted from https://stackoverflow.com/questions/43831880/pylucene-how-to-use-bm25-similarity-instead-of-tf-idf
        #  and https://stackoverflow.com/questions/39182236/how-to-rank-documents-using-tfidf-similairty-in-lucene
        # parse the query
        parser = queryparser.classic.QueryParser(field_to_search, analyzer)  # our field is called text
        query = parser.parse(query_text)
        hits = i_searcher.search(query, search_limit_count).scoreDocs
        ans = []
        for hit in hits:
            # print('hit data', hit)
            hit_doc = i_searcher.doc(hit.doc)
            # print(hit_doc['title'], hit.score)
            answer = [hit_doc['title'], hit.score, hit_doc[field_to_search]]
            ans.append(answer)
        i_reader.close()
        directory.close()
        return ans


def build_file_dump():
    # input_path = "src/main/resources/enwiki-20140602-pages-articles.xml-0005.txt"
    # input_path = "src/main/resources/enwiki-20140602-pages-articles.xml-0006.txt"  # has cairo
    ######################################################
    txt_files = glob.glob("src/main/resources/e*.txt")
    # txt_files = ["src/main/resources/enwiki-20140602-pages-articles.xml-0005.txt"]
    # print(txt_files)
    # file dump God willing
    # short_dump_file_name = "file_parsed_json.txt"
    # long_dump_file_name = "full_file_parsed_json.txt"
    # test_dump_file_name = "file_parsed_json_test.txt"
    # parse_dump_files(txt_files, max_doc_len)
    # parse_dump_files(txt_files, long_dump_file_name, None)
    max_doc_len = MAX_DOC_LENGTH
    # short_dump_file_name = "parse_json_stop_lem_4k.txt"
    s_dump_file_stop_no_lemma = "parse_json_stop_no_lem_4k.txt"
    l_dump_file_stop_no_lemma = "parse_json_stop_no_lem.txt"

    do_no_lemma = None
    no_max_len = None
    parse_dump_files(txt_files, s_dump_file_stop_no_lemma, max_doc_len, do_no_lemma)
    parse_dump_files(txt_files, l_dump_file_stop_no_lemma, no_max_len, do_no_lemma)

    l_dump_file_stop_lemma = "parse_json_stop_lem.txt"
    do_lemma = True
    parse_dump_files(txt_files, l_dump_file_stop_lemma, no_max_len, do_lemma)
    # max_doc_len = 2000
    # short_dump_file_name = "parse_json_no_lem_2k.txt"
    # def parse_dump_files(text_file_list, dump_file_name, max_doc_len, do_lemma=None)
    # parse_dump_files(txt_files, short_dump_file_name, max_doc_len, None)
    pass


def build_index():
    ###############################################
    # Build the index
    ###############################################
    # ####### LIST containing ALL TEXT FILES #######
    # txt_files = glob.glob("src/main/resources/e*.txt")
    # max_doc_len = MAX_DOC_LENGTH
    # data_files_params = [txt_files, max_doc_len]
    data_files_params = None
    # New index (w) or appending to index (a)
    first_build_mode = "w"
    # add_on_mode = "a"
    # max_doc_len = None
    # index_to_use = DEFAULT_INDEX_DIRECTORY_CATS
    # index_to_use = ENG_INDEX_DIRECTORY
    # index_to_use = SHORT_INDEX_LEMMA
    # index_to_use = ENG_SHORT_INDEX_LEMMA
    # index_to_use = DEFAULT_INDEX_SHORT_CATS

    # SHORT_INDEX_CATS_2K = "index2k"
    # SHORT_INDEX_CATS_4K = "index4k"
    # pre_calc_opts = {"short": {"file": "parse_json_stop_no_lem_4k.txt", "index_dir": ENG_STOP_NO_LEMMA_4K},
    #                  "long": {"file": "parse_json_stop_no_lem.txt", "index_dir": ENG_STOP_NO_LEMMA}}
    # pre_calc_opts = {"short": {"file": "file_parsed_json.txt", "index_dir": SHORT_INDEX_LEMMA},
    #                  "long": {"file": "full_file_parsed_json.txt", "index_dir": LONG_INDEX_LEMMA}}
    # pre_calc_opts = {"short": {"file": "file_parsed_json.txt", "index_dir": ENG_SHORT_INDEX_LEMMA}, "long": {"file": "full_file_parsed_json.txt", "index_dir": ENG_LONG_INDEX_LEMMA}}
    # pre_calc_opts = {"short": {"file": "parse_json_stop_lem_4k.txt", "index_dir": LEMMA_4K},
    #                  "long": {"file": "parse_json_stop_lem.txt", "index_dir": LEMMA_FULL}}
    pre_calc_opts = {"short": {"file": "parse_json_stop_no_lem.txt", "index_dir": ENG_STOP_NO_LEMMA_TF}}
    sim_method = "tfidf"

    for opt in pre_calc_opts:
        # print("Option is: ", pre_calc_opts[opt]["file"], pre_calc_opts[opt]["index_dir"])
        build_index_eng(data_files_params, pre_calc_opts[opt]["file"], pre_calc_opts[opt]["index_dir"], sim_method)
        # build_index_std(data_files_params, pre_calc_opts[opt]["file"], pre_calc_opts[opt]["index_dir"], first_build_mode)
    # my_analyzer = None
    # do_lemma = True
    # data_pre_calc = None
    # build_index(data_files, max_doc_len, data_pre_calc, index_directory=None, index_mode=None)  # RAM directory
    # build_index(txt_files, max_doc_len, data_pre_calc, DEFAULT_INDEX_DIRECTORY, first_build_mode)
    # build_index(txt_files, max_doc_len, data_pre_calc, DEFAULT_INDEX_DIRECTORY_CATS, first_build_mode)
    # build_index(txt_files, max_doc_len, data_pre_calc, ENG_INDEX_DIRECTORY, first_build_mode, analyzer="EnglishAnalyzer")
    #   def build_index_eng(data_files, max_doc_len=None, data_pre_calc, index_directory, index_mode=None):
    # build_index_eng(txt_files, max_doc_len, data_pre_calc, ENG_INDEX_DIRECTORY, first_build_mode)
    #   def build_index(data_files, max_doc_len=None, data_pre_calc=None, index_directory=None, index_mode=None, analyzer=None, do_lemma=None):
    # build_index(None, None, "file_parsed_json.txt", SHORT_INDEX_LEMMA, first_build_mode, None, None) # SHORT - lemma:
    # build_index(None, None, "full_file_parsed_json.txt", LONG_INDEX_LEMMA, first_build_mode, None, None)  # LONG - lemma
    # ###############################################
    #     input_path = "src/main/resources/input2.txt"
    # input_path = "src/main/resources/enwiki-20140602-pages-articles.xml-0005.txt"
    # input_path = "src/main/resources/enwiki-20140602-pages-articles.xml-0006.txt"  # has cairo
    # prints the result of text parsing:
    # for doc in doc_t_c_t_h_list:
    #     # if doc[title_index] == "Cairo":
    #     #     print(doc[title_index], doc[category_index])
    #     print(doc[title_index], doc[category_index])
    ################################################
    pass


def get_failed_questions():
    dump_file_name = "failed_questions.txt"
    failed_questions = read_json_list_dump(dump_file_name)
    return failed_questions


def get_all_questions():
    questions_path = "src/main/resources/questions.txt"
    questions_list = read_questions_file(questions_path)  # returns list of: category, question, answer
    questions_list.sort(key=itemgetter(0))
    return questions_list


def get_test_question():
    ######################################
    # uncomment for test run @ following lines
    question_list = []
    # curr_question = "Several bridges, including El Tahrir, cross the Nile in this capital"
    # curr_answer = "Cairo"
    # curr_category = "AFRICAN CITIES"
    curr_question = 'In an essay defending this 2011 film, Myrlie Evers-Williams said, "My mother was" this film "& so was her mother"'
    curr_category = "AFRICAN-AMERICAN WOMEN"
    curr_answer = "The Help"
    question_list.append([curr_category, curr_question, curr_answer])
    # ans1 = QueryEngine(input_path).run_query(test_question)  # God willing can uncomment later (single file)
    # ans1 = QueryEngine(txt_files).run_query(test_question)  # God willing can uncomment later (single file)
    # ans1 = QueryEngine(DEFAULT_INDEX_DIRECTORY).run_query(test_question)  # God willing  directory for index given
    return question_list


def run_questions():
    ######################################################
    # get questions
    questions_list = get_all_questions()
    # questions_list = get_test_question()
    # questions_list = get_failed_questions()
    # for q in questions_list:
    #     print(q)
    print("Num questions: ", len(questions_list))
    category_index = 0
    question_index = 1
    answer_index = 2
    spacy_lemma = "lemma"
    spacy_lemma_relax = "lemma_relax"
    stem_only = "stem_only"

    # similarity_method = ["tfidf"]
    similarity_method = ["bm25"]
    # similarity_method = ["bm25", "tfidf"]
    # num_results = 10  # top ten results
    # num_results = 1  # top 1 results
    # use_categories = ["Yes"]
    # use_categories = ["No"]
    # query_combinations = [{"stem": stem_none, "index": DEFAULT_INDEX_DIRECTORY_CATS},
    #                       {"stem": stem_none, "index": SHORT_INDEX_LEMMA},
    #                       {"stem": stem_none, "index": LONG_INDEX_LEMMA},
    #                       {"stem": stem_eng, "index": ENG_SHORT_INDEX_LEMMA},
    #                       {"stem": stem_eng, "index": ENG_LONG_INDEX_LEMMA}]
    # query_combinations = [{"stem": stem_eng, "index": ENG_LONG_INDEX_LEMMA}]  # best combination
    # query_combinations = [{"stem": stem_none, "index": SHORT_INDEX_CATS_2K},
    #                       {"stem": stem_none, "index": ENG_INDEX_DIRECTORY},
    #                       {"stem": stem_eng, "index": ENG_SHORT_INDEX_LEMMA},
    #                       {"stem": stem_eng, "index": ENG_LONG_INDEX_LEMMA}]
    # query_combinations = [{"stem": stem_eng, "index": ENG_LONG_INDEX_LEMMA}]
    # query_combinations = [{"stem_lem": stem_none, "index": DEFAULT_INDEX_DIRECTORY},
    #                       {"stem_lem": stem_eng, "index": ENG_STOP_NO_LEMMA},
    #                       {"stem_lem": stem_spacy, "index": LEMMA_FULL}]
    # stem_combinations = [stem_eng, stem_spacy]
    # index_options = [DEFAULT_INDEX_DIRECTORY, ENG_STOP_NO_LEMMA, LEMMA_FULL, LONG_INDEX_LEMMA, ENG_LONG_INDEX_LEMMA]
    # index_options = [LEMMA_FULL]
    # index_options = [DEFAULT_INDEX_DIRECTORY]
    # index_options = [DEFAULT_INDEX_DIRECTORY_CATS]
    # stem_lem_options = ["None", stem_only, spacy_lemma]
    # stem_lem_options = ["None", stem_only, spacy_lemma]
    # stem_lem_options = ["None"]
    # use_categories = ["Yes", "No"]
    # index_options = [ENG_STOP_NO_LEMMA_4K, LEMMA_4K]
    # stem_lem_options = [stem_only, spacy_lemma]
    # index_options = [ENG_STOP_NO_LEMMA_4K, LEMMA_4K]
    # stem_lem_options = ["None", stem_only, spacy_lemma]
    use_categories = ["Yes"]
    # use_categories = ["No", "Yes"]
    index_options = [ENG_LONG_INDEX_LEMMA]  # the index with stem + lemma
    # index_options = [ENG_INDEX_DIRECTORY]
    # stem_lem_options = ["None", spacy_lemma_relax, stem_only]
    # stem_lem_options = ["None", stem_only, spacy_lemma_relax]
    stem_lem_options = [stem_only]
    # stem_lem_options = [stem_only, spacy_lemma_relax]
    # stem_lem_options = [spacy_lemma_relax]
    best_score = 0
    best_opt = ""
    fail_qs = []
    # dump_file_name = "failed_questions.txt"
    for sim in similarity_method:
        for i_option in index_options:
            # if curr_stem is None:
            #     str_curr_stem = "None"
            # curr_index = option["index"]
            # opt_string = "Index: " + curr_index + " Stem: " + str_curr_stem
            for stem_lem in stem_lem_options:
                for cat in use_categories:
                    opt_string = "Sim: " + sim + " Index: " + i_option + " Stem_Lem: " + stem_lem + " use categories: " + cat
                    print('Starting God willing: ', opt_string)
                    match_count = 0
                    fail_count = 0
                    match_title = ""
                    match_doc = ""
                    for q in questions_list:  # for q in questions_list[1:10]:
                        curr_answer = q[answer_index]
                        curr_answer_list = curr_answer.split("|")
                        curr_category = q[category_index]
                        curr_question = q[question_index]
                        if cat == "Yes":
                            # print("use categories, God willing")
                            # curr_question = curr_question + ' ' + curr_category
                            curr_question = curr_question + ' ' + curr_category.lower()
                            # if curr_index in [SHORT_INDEX_LEMMA, LONG_INDEX_LEMMA, ENG_SHORT_INDEX_LEMMA,
                            #                   ENG_LONG_INDEX_LEMMA]:
                            #     curr_question = lemmatize_string(curr_question)
                            # print("Lemma, God willing")
                        clean_question = clean_query(curr_question)
                        stem_parameter = None
                        if stem_lem == spacy_lemma:
                            clean_question = lemmatize_string(clean_question)
                        if stem_lem == stem_only:
                            clean_question = remove_stop_words(clean_question)
                            stem_parameter = "English"
                        if stem_lem == spacy_lemma_relax:
                            stem_parameter = "English"
                            clean_question = lemmatize_string(clean_question, None, True, True)
                        #######################################
                        # Only use if query lemma needed
                        #  adjective, proper noun, noun
                        # lemmatize_string(query_data, retain_pos_tags=None, token_or_lemma=None):
                        # retain_pos_tags = ['ADJ', 'PROPN', 'NOUN', 'X', 'NUM']
                        # retain_pos_tags = ['ADJ', 'PROPN', 'NOUN']
                        # word_to_keep = "token"  # word_to_keep = "lemma"
                        # if clean_question.count(' ') > 3:  # words
                        #     clean_question = lemmatize_string(clean_question, retain_pos_tags, word_to_keep)  # also lemmatize the query
                        #######################################
                        # ans1 = QueryEngine(index_to_use).run_query_bm25(curr_question)
                        # ans1 = QueryEngine(index_to_use).run_query_bm25(clean_question)
                        # match_count = 0
                        # fail_count = 0

                        # ans1 = QueryEngine(curr_index).run_query(clean_question, sim, curr_stem, num_results)
                        # num_results = 50
                        num_results = 25
                        # print("Examining: ", clean_question)
                        # ans1 = QueryEngine(i_option).run_query_get_doc(clean_question, sim, num_results)
                        ans1 = QueryEngine(i_option).run_query_get_doc(clean_question, sim, num_results, stem_parameter)
                        ans_match_found = False
                        match_position = 0
                        match_score = 0
                        match_title = ""
                        match_doc = ""
                        match_list_str = ""
                        for a in ans1:  # God willing can uncomment later
                            # result_title = a.get("doc_id")
                            match_position += 1
                            match_title = a[0]  # [title, score]
                            # print("Examining answer: ", match_title)
                            # if contains_stop_word(match_title, clean_question):  # string-to-examine, stop-words
                            # ### A_NOT_Q Block ###
                            if contains_stop_word(match_title, remove_stop_words(clean_question)):  # string-to-examine, stop-words
                                # print(match_position, " discarding: ", match_title)
                                continue  # get the next result
                            match_score = a[1]
                            # match_doc = a[2]
                            match_list_str += match_title + '|' + str(match_score) + '| '
                            # if result_title == curr_answer:
                            if match_title in curr_answer_list:
                                ans_match_found = True
                            else:
                                ans_match_found = False
                            break  # first time you get past the stopword conditional - it's over.
                        if ans_match_found:
                            match_count += 1
                            # print("PASS: ", match_position, "|Score: ", match_score, "|", clean_question, "|", '#'.join(curr_answer_list), "|", match_title, "|", match_list_str)
                        else:
                            fail_count += 1
                            # print("FAIL: ", len(ans1), "|Score: ", match_score, "|", clean_question, "|", '#'.join(curr_answer_list), "|", "_NOT_FOUND_", "|", match_list_str)
                            # print(clean_question, curr_answer_list, "-", result_title)
                            fail_qs.append([q[category_index], q[question_index], q[answer_index]])
                    # print("Title: ", match_title)
                    # print("Doc: ", match_doc[0:500])
                    print(opt_string, "Precision @ 1 percentage (Total matches): ", match_count, "Total fails: ", fail_count)
                    if match_count > best_score:
                        best_score = match_count
                        best_opt = opt_string
    print("=============================== \nBest Precision @ 1: ", best_opt, "  score: ", best_score)
    # write_list_to_json(dump_file_name, fail_qs)


def main():
    # can comment this out later
    # first process text incl. lemmatization and save locally (not docker)
    # since spacy runs faster locally than in VM
    ######################################################
    # build_file_dump()

    ######################################################
    # next build index.
    # build_index()

    ######################################################
    # Run Questions
    # #### Convert Questions to List #### #
    run_questions()
    # print(OVERLAP_ARRAY)
    # "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "if", "in", "into", "is", "it", "no", "not", "of", "on", "or", "such", "that", "the", "their", "then", "there", "these", "they", "this", "to", "was", "will", "with"
    # result = "This is a test of the english stop analyzer by the people for the people if the people it no not of on such that the then ".split()
    # stop = analysis.StopAnalyzer(EnglishAnalyzer.ENGLISH_STOP_WORDS_SET)
    # result = analysis.StopFilter(result, EnglishAnalyzer.ENGLISH_STOP_WORDS_SET)
    # stop_words = "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "if", "in", "into", "is", "it", "no", "not", "of", "on", "or", "such", "that", "the", "their", "then", "there", "these", "they", "this", "to", "was", "will", "with"
    # result_new = []


if __name__ == "__main__":
    main()
