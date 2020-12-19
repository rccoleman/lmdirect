from mitmproxy import http
from mitmproxy import ctx

TOKEN_URL = "https://cms.lamarzocco.io/oauth/v2/token"

def request(flow: http.HTTPFlow) -> None:
    if flow.request.url == TOKEN_URL:
        print(f"client_id: {flow.request.urlencoded_form['client_id']}")
        print(f"client_secret: {flow.request.urlencoded_form['client_secret']}")
        print(f"username: {flow.request.urlencoded_form['username']}")
        print(f"password: {flow.request.urlencoded_form['password']}")
        ctx.master.shutdown()
