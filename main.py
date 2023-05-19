from pathlib import Path

import quart
import quart_cors
import requests
import yaml
from quart import request

app = quart_cors.cors(quart.Quart(__name__), allow_origin="https://chat.openai.com")


@app.route("/", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def proxy_request(path=""):
    url = f"https://api.github.com/{path}"

    data = await request.get_data()
    # log all request options

    response = requests.request(
        method=request.method,
        url=url,
        data=data,
        cookies=request.cookies,
        allow_redirects=False,
    )
    return quart.Response(
        response=response.content,
        status=response.status_code,
        # headers=dict(response.headers),
        mimetype=response.headers.get("content-type", None),
    )


@app.get("/logo.png")
async def plugin_logo():
    filename = "logo.png"
    return await quart.send_file(filename, mimetype="image/png")


@app.get("/.well-known/ai-plugin.json")
async def plugin_manifest():
    with open("./.well-known/ai-plugin.json") as f:
        text = f.read()
        return quart.Response(text, mimetype="text/json")


CACHE_FILE = Path("github_api.yaml")

OPENAPI_PLUGIN = Path("openapi.yaml")


@app.get("/openapi.yaml")
async def openapi_spec():
    if OPENAPI_PLUGIN.exists():
        text = OPENAPI_PLUGIN.read_text()
    else:
        host = request.headers["Host"]
        if CACHE_FILE.exists():
            text = CACHE_FILE.read_text()
        else:
            url = "https://raw.githubusercontent.com/github/rest-api-description/main/descriptions/api.github.com/api.github.com.yaml"
            response = requests.get(url)
            text = response.text
            CACHE_FILE.write_text(response.text)
        github_text = text.replace("https://api.github.com", "http://localhost:5003").replace(
            "http://api.github.com", "http://localhost:5003"
        )
        github_spec = yaml.safe_load(github_text)
        spec = {
            "openapi": github_spec["openapi"],
            "info": {
                "title": "Unofficial Github Plugin",
                "description": "Unofficial Github Plugin for OpenAI Chat",
                "version": "v1",
            },
            "servers": [{"url": "http://localhost:5003"}],
            "paths": dict(list(github_spec["paths"].items())[:200]),
            "components": {"schemas": dict(list(github_spec["components"]["schemas"].items())[:200])},
        }
        # Change all the operationIds to be unique and smaller than length 300
        operationid = 0
        for path in spec["paths"].values():
            for operation in path.values():
                operation["operationId"] = f"operation_{operationid}"
                operationid += 1
                operation['description'] = operation['description'][:300]

        text = yaml.dump(spec)
        # Switch all lines that end in - null to - "null"
        # {"detail":"Error setting localhost plugin: {\"validation_errors\":[{\"loc\":[\"enum\",9],\"msg\":\"none is not an allowed value\",\"type\":\"type_error.none.not_allowed\"}],\"message\":\"1 validation error for StringSchema\\nenum -> 9\\n  none is not an allowed value (type=type_error.none.not_allowed)\"}"}
        text = "\n".join(
            line if not line.strip().endswith("- null") else line.replace("- null", '- "null"')
            for line in text.split("\n")
        )
        OPENAPI_PLUGIN.write_text(text)
    return quart.Response(text, mimetype="text/yaml")


def main():
    app.run(debug=True, host="0.0.0.0", port=5003)


if __name__ == "__main__":
    main()
