import re
from fastapi import HTTPException, UploadFile

class ResumeService:
    @staticmethod
    async def parse_resume(file: UploadFile) -> dict:
        try:
            content = await file.read()
            if file.filename.endswith(".txt"):
                text = content.decode("utf-8", errors="ignore")
            else:
                text = content.decode("latin-1", errors="ignore")
                text = re.sub(r'[^\x20-\x7E\n\r\t]', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
            return {"text": text[:8000], "filename": file.filename}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")
