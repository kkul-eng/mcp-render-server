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
    allow_origins=["*"],  # Tüm kaynaklar için erişime izin ver
    allow_credentials=True,
    allow_methods=["*"],  # Tüm HTTP metotlarına izin ver
    allow_headers=["*"],  # Tüm başlıklara izin ver
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

@app.get("/health")
async def health_check():
    """Sunucu sağlık kontrolü"""
    return {"status": "ok", "service": "mcp-server"}

@app.post("/mcp")
async def run_mcp(query: dict = Body(...)):
    """
    MCP aracını çalıştır
    
    Örnek istek body:
    ```json
    {
        "tool": "read_file",
        "args": {
            "path": "sample.txt"
        }
    }
    ```
    """
    try:
        # Debug için gelen isteği logla
        print(f"Gelen istek: {query}")
        
        tool_name = query.get("tool", "read_file")
        args = query.get("args", {"path": "sample.txt"})
        
        # Araç çalıştırma işlemini logla
        print(f"Çalıştırılıyor: tool={tool_name}, args={args}")
        
        # Aracı çalıştır
        result = mcp.run_tool(tool_name, **args)
        
        # Sonucu döndür
        return {"result": result}
    except Exception as e:
        # Hata detaylarını logla
        error_msg = str(e)
        stack_trace = traceback.format_exc()
        print(f"Hata: {error_msg}\n{stack_trace}")
        
        # Hata yanıtı döndür
        raise HTTPException(status_code=500, detail=f"MCP Hatası: {error_msg}")

# Test için basit bir endpoint
@app.get("/")
async def root():
    return {"message": "MCP Server çalışıyor", "info": "POST /mcp ile istek yapabilirsiniz"}

# Uygulama başlat
if __name__ == "__main__":
    import uvicorn
    
    # Render'ın belirlediği port veya varsayılan 8000
    port = int(os.getenv("PORT", 8000))
    
    # Debug modunda çalıştır
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="debug")
