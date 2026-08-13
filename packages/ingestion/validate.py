from fastapi import HTTPException
ALLOWED_EXT={".pdf",".docx",".txt"}
ALLOWED_MIME={"application/pdf","application/vnd.openxmlformats-officedocument.wordprocessingml.document","text/plain","application/octet-stream"}

def validate_upload(filename:str,mime:str,data:bytes,max_mb:int):
    from pathlib import Path
    ext=Path(filename).suffix.lower()
    if ext not in ALLOWED_EXT: raise HTTPException(415,"Unsupported file extension")
    if mime and mime not in ALLOWED_MIME: raise HTTPException(415,"Unsupported MIME type")
    if not data: raise HTTPException(400,"Empty file")
    if len(data)>max_mb*1024*1024: raise HTTPException(413,f"File exceeds {max_mb} MB")
    if ext=='.pdf' and not data.startswith(b'%PDF-'): raise HTTPException(415,"Invalid PDF signature")
    if ext=='.docx' and not data.startswith(b'PK'): raise HTTPException(415,"Invalid DOCX signature")
