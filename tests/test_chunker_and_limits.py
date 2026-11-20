from src.llm_engine.chunker import IntelligentChunker


def test_html_cleaning():
    chunker = IntelligentChunker()
    dirty_html = """
    <html>
        <head><style>.ad { display: none; }</style></head>
        <body>
            <nav><a href='/home'>Home</a></nav>
            <h1>OpenAI Announces GPT-5</h1>
            <p>Frontier intelligence breakthrough with reasoning capabilities.</p>
            <script>console.log('tracker');</script>
            <footer>Copyright 2026</footer>
        </body>
    </html>
    """
    clean_text = chunker.clean_html(dirty_html)
    assert "OpenAI Announces GPT-5" in clean_text
    assert "Frontier intelligence breakthrough" in clean_text
    assert "console.log" not in clean_text
    assert ".ad {" not in clean_text


def test_chunking_prevents_413():
    # Set a tiny max_tokens to force chunking
    chunker = IntelligentChunker(max_tokens=100)
    huge_text = "This is a sentence about AI models and enterprise pricing. " * 50

    chunks = chunker.chunk_payload(huge_text, is_html=False)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= chunker.max_chars + 100

    # Truncation guarantee
    summary = chunker.truncate_to_dense_summary(huge_text)
    assert len(summary) <= chunker.max_chars + 100
