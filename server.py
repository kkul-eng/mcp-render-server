from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI
from mcp.server.sse import sse_middleware

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

sse_middleware(app, mcp)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
