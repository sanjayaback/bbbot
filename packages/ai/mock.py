import hashlib
import math
import re
from collections.abc import AsyncIterator
from apps.api.config import settings


class MockEmbedder:
    model="mock-embedding-v1"
    async def embed(self,text:str)->list[float]:
        vec=[0.0]*settings.embedding_dimension
        for token in re.findall(r"[\w\u0900-\u097F]+",text.lower()):
            digest=hashlib.sha256(token.encode()).digest()
            idx=int.from_bytes(digest[:4],"big")%len(vec)
            vec[idx]+=1.0 if digest[4]%2 else -1.0
        norm=math.sqrt(sum(x*x for x in vec)) or 1.0
        return [x/norm for x in vec]


class MockLLM:
    model="mock-grounded-v1"
    async def stream_answer(self,question:str,context:str)->AsyncIterator[str]:
        if not context.strip():
            answer="I could not find this information in the uploaded documents."
        else:
            passages=[]
            for block in context.split('--- SOURCE ')[1:]:
                body=block.split('---\n',1)[-1].strip()
                if body:
                    passages.append(body)
            excerpt=(passages[0] if passages else context).strip().replace('\n',' ')
            answer=f"Based on the retrieved document evidence: {excerpt[:700]}"
        for i in range(0,len(answer),28):
            yield answer[i:i+28]
