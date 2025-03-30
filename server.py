from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP
import os
import traceback

# FastAPI uygulamasını başlat
app = FastAPI(title="MCP Server API", 
              description="MicroCommand Protocol (MCP) sunucusu",
              version="1.0.0")

# CORS ayarlarını ekle
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MCP nesnesini oluştur
mcp = FastMCP("filesystem")

@mcp.tool()
def read_file(path: str) -> str:
    """Belirtilen yoldaki dosyayı okur"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Dosya bulunamadı"
    except Exception as e:
        return f"Dosya okuma hatası: {str(e)}"

@mcp.tool()
def document_qa(question: str, doc_name: str = "izahname.txt") -> str:
    """İzahnamede soru yanıtlar"""
    try:
        # Debug için çalışma dizinini ve mevcut dosyaları yazdır
        print(f"Çalışma dizini: {os.getcwd()}")
        print(f"Aranan dosya: {doc_name}")
        print(f"Mevcut dosyalar: {os.listdir('.')}")
        
        # Dokümanı doğrudan kök dizinden oku
        doc_path = doc_name
        
        with open(doc_path, "r", encoding="utf-8") as f:
            document = f.read()
        
        # Dokümanı paragraflara böl
        paragraphs = document.split('\n\n')
        
        # Soru kelimelerini tespit et (stopwords hariç)
        question_words = [w.lower() for w in question.split() if len(w) > 3]
        
        # En alakalı paragrafları bul
        relevant_paragraphs = []
        for p in paragraphs:
            score = sum(1 for word in question_words if word.lower() in p.lower())
            if score > 0:
                relevant_paragraphs.append((score, p))
        
        # Skorlarına göre sırala
        relevant_paragraphs.sort(reverse=True)
        
        if relevant_paragraphs:
            # En alakalı 2 paragrafı döndür
            result = "\n\n".join([p for _, p in relevant_paragraphs[:2]])
            return result
        else:
            return "Üzgünüm, izahnamede bu soruya yanıt bulunamadı."
    except FileNotFoundError:
        return f"Doküman bulunamadı: {doc_name}"
    except Exception as e:
        return f"QA hatası: {str(e)}"

@app.get("/")
async def root():
    return {"message": "MCP Server çalışıyor", "info": "POST /mcp ile istek yapabilirsiniz"}

@app.post("/mcp")
async def run_mcp(query: dict = Body(...)):
    """
    MCP aracını çalıştır
    """
    try:
        # Debug için gelen isteği logla
        print(f"Gelen istek: {query}")
        
        tool_name = query.get("tool", "read_file")
        args = query.get("args", {"path": "sample.txt"})
        
        # Araç çalıştırma işlemini logla
        print(f"Çalıştırılıyor: tool={tool_name}, args={args}")
        
        # Doğru metodu kullanarak aracı çalıştır
        if tool_name == "read_file":
            result = read_file(**args)
        elif tool_name == "document_qa":
            result = document_qa(**args)
        else:
            raise ValueError(f"Bilinmeyen araç: {tool_name}")
        
        # Sonucu döndür
        return {"result": result}
    except Exception as e:
        # Hata detaylarını logla
        error_msg = str(e)
        stack_trace = traceback.format_exc()
        print(f"Hata: {error_msg}\n{stack_trace}")
        
        # Hata yanıtı döndür
        raise HTTPException(status_code=500, detail=f"MCP Hatası: {error_msg}")

# Uygulama başlat
if __name__ == "__main__":
    import uvicorn
    
    # Render'ın belirlediği port veya varsayılan 8000
    port = int(os.getenv("PORT", 8000))
    
    # Debug modunda çalıştır
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="debug")
