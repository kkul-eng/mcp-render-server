from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI

app = FastAPI()
mcp = FastMCP("filesystem")

@mcp.tool()
def read_file(path: str) -> str:
    """Belirtilen yoldaki dosyayı okur"""
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return "Dosya bulunamadı"
    except Exception as e:
        return f"Hata: {str(e)}"

@app.post("/mcp")
async def run_mcp(query: dict):
    try:
        tool_name = query.get("tool", "read_file")
        args = query.get("args", {"path": "sample.txt"})
        
        if tool_name == "read_file":
            result = read_file(**args)
        else:
            result = "Bilinmeyen tool çağrıldı."
        
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

    uvicorn.run(app, host="0.0.0.0", port=8000)
    uvicorn.run(app, host="0.0.0.0", port=8000)
