import pytest
from fastapi import HTTPException
from packages.ingestion.validate import validate_upload

def test_pdf_signature():
    validate_upload('a.pdf','application/pdf',b'%PDF-1.7 test',20)

def test_reject_fake_pdf():
    with pytest.raises(HTTPException): validate_upload('a.pdf','application/pdf',b'MZfake',20)
