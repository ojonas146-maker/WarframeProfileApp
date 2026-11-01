"""Ponto de entrada no Android: sobe o server.py numa porta local aleatória (127.0.0.1) e devolve a porta."""
import os, threading

_port = 0


def start(home, token):
    global _port
    if _port:
        return _port
    os.environ["WF_HOME"] = home
    os.environ["WF_APP"] = "1"
    os.environ["WF_TOKEN"] = token
    import server
    from http.server import ThreadingHTTPServer
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.H)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True, name="wf-http").start()
    _port = httpd.server_address[1]
    return _port
