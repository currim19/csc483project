from unittest import TestCase
from src.main.python.edu.arizona.cs.query_engine import QueryEngine
from src.main.python.edu.arizona.cs.document import Document


class Test_hw2_q7(TestCase):
    input_path = "src/main/resources/input.txt"

    def test_q7_1_1(self):
        query = ["information", "retrieval"]
        ans_q1_1 = QueryEngine(self.input_path).q1_1(query)
        assert type(ans_q1_1) is not None
        assert type(ans_q1_1) is list
        assert len(ans_q1_1) > 0
        assert len(ans_q1_1) == 2

        doc_names_q1 = ["Doc1", "Doc2"]
        counter = 0

        for docs in ans_q1_1:
            assert doc_names_q1[counter] == docs.doc_id
            counter = counter + 1

    def test_q7_1_2_a(self):
        query = ["information", "retrieval"]
        ans = QueryEngine(self.input_path).q1_2_a(query)
        assert type(ans) is not None
        assert type(ans) is list
        assert len(ans) > 0
        assert len(ans) == 2

        expected_doc_names = ["Doc1", "Doc2"]
        counter1 = 0

        for docs in ans:
            assert expected_doc_names[counter1] == docs.doc_id
            counter1 = counter1 + 1

    def test_q7_1_2_b(self):
        query = ["information", "retrieval"]
        ans = QueryEngine(self.input_path).q1_2_b(query)
        assert type(ans) is not None
        assert type(ans) is list
        assert len(ans) == 0

    def test_q7_1_2_c(self):
        query = ["information", "retrieval"]
        ans = QueryEngine(self.input_path).q1_2_c(query)
        assert type(ans) is not None
        assert type(ans) is list
        assert len(ans) > 0
        assert len(ans) == 1

        expected_doc_names = ["Doc1"]
        counter1 = 0

        for docs in ans:
            assert expected_doc_names[counter1] == docs.doc_id
            counter1 = counter1 + 1

    def test_q7_1_3(self):
        query = ["information", "retrieval"]
        ans = QueryEngine(self.input_path).q1_3(query)
        assert type(ans) is not None
        assert type(ans) is list
        assert len(ans) > 0
        assert len(ans) == 2

        expected_doc_names = ["Doc1", "Doc2"]
        counter1 = 0

        for docs in ans:
            assert expected_doc_names[counter1] == docs.doc_id
            counter1 = counter1 + 1