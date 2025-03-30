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

@app.post("/mcp")
async def run_mcp(query: dict):
    tool_name = query.get("tool", "read_file")
    args = query.get("args", {"path": "sample.txt"})
    result = mcp.run_tool(tool_name, **args)
    return {"result": result}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
