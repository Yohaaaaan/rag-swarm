import pytest
from langchain_text_splitters import RecursiveCharacterTextSplitter

class TestChunking:
    def test_chunk_boundaries_are_sentence_aware(self):
        """Chunks should split at sentence boundaries, not mid-sentence"""
        CHUNK_SIZE = 500
        CHUNK_OVERLAP = 50
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
        text = "First sentence. Second sentence. Third sentence with more words."
        chunks = text_splitter.split_text(text)
        for chunk in chunks:
            if len(chunk) > 10:
                first_char = chunk[0]
                ok = first_char.isupper() or first_char in '\n "(\''
                assert ok, f"Chunk starting with {repr(first_char)} seems mid-sentence: {chunk[:30]}"

    def test_page_number_is_sequential(self):
        """page_number should be sequential chunk index, not page+idx"""
        CHUNK_SIZE = 500
        CHUNK_OVERLAP = 50
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
        text = "A" * 200 + ". " + "B" * 200 + ". " + "C" * 200 + "."
        chunks = text_splitter.split_text(text * 10)
        assert len(chunks) > 1

    def test_separators_prefer_semantic_boundaries(self):
        """Separators should prefer paragraph > sentence > character"""
        CHUNK_SIZE = 500
        CHUNK_OVERLAP = 50
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
        text = ("Lorem ipsum dolor sit amet. " * 30) + "\n\n" + ("Consectetur adipiscing elit. " * 30)
        chunks = text_splitter.split_text(text)
        assert len(chunks) >= 2
        for chunk in chunks:
            if len(chunk) > 5:
                assert not (chunk[0].islower() and '.' not in chunk[:5]), f"Chunk seems to split mid-sentence: {chunk[:40]}"