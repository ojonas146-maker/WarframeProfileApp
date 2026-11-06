"""Presença no warframe.market (online / em jogo / invisível) pelo WebSocket v2 — mesmo protocolo do seu wfmb3.js:
wss://ws.warframe.market/socket?platform=pc, subprotocolo "wfm", @wfm|cmd/auth/signIn e @wfm|cmd/status/set.
Cliente WebSocket mínimo (só biblioteca padrão). Mantém a conexão aberta enquanto o app estiver rodando."""
import base64, hashlib, json, os, socket, ssl, struct, threading, time
import settings, wfmacct

TARGET = ("ws.warframe.market", 443, True)   # (host, porta, tls) — trocado nos testes
PATH = "/socket?platform=pc"
UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
DURATION = 3600
_st = {"desired": "", "connected": False, "authed": False, "last": "", "err": ""}
_thr = [None]
_stop = threading.Event()


class _WS:
    def __init__(self, host, port, tls, path, origin, proto):
        raw = socket.create_connection((host, port), timeout=20)
        self.s = ssl.create_default_context().wrap_socket(raw, server_hostname=host) if tls else raw
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
                        "Sec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: %s\r\nOrigin: %s\r\nUser-Agent: %s\r\n\r\n"
                        % (path, host, key, proto, origin, UA)).encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            c = self.s.recv(4096)
            if not c:
                raise OSError("servidor fechou durante o handshake")
            buf += c
        head, _, rest = buf.partition(b"\r\n\r\n")
        if b" 101 " not in head.split(b"\r\n")[0]:
            raise OSError("handshake recusado: " + head.split(b"\r\n")[0].decode("latin1")[:80])
        self.buf, self.frag, self.fop = rest, b"", 0

    def _need(self, n, timeout):
        self.s.settimeout(timeout)
        while len(self.buf) < n:
            c = self.s.recv(65536)
            if not c:
                raise OSError("conexão fechada")
            self.buf += c
        d, self.buf = self.buf[:n], self.buf[n:]
        return d

    def send_frame(self, op, payload=b""):
        n, hdr = len(payload), bytearray([0x80 | op])
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            hdr += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mk = os.urandom(4)
        self.s.settimeout(15)
        self.s.sendall(bytes(hdr) + mk + bytes(b ^ mk[i % 4] for i, b in enumerate(payload)))

    def send(self, text):
        self.send_frame(0x1, text.encode("utf-8"))

    def recv(self, timeout=2.0):
        """-> (opcode, bytes) ou None se nada chegou no tempo."""
        try:
            h = self._need(2, timeout)
        except (socket.timeout, ssl.SSLWantReadError):
            return None
        fin, op, ln, masked = h[0] & 0x80, h[0] & 0x0F, h[1] & 0x7F, h[1] & 0x80
        if ln == 126:
            ln = struct.unpack(">H", self._need(2, 15))[0]
        elif ln == 127:
            ln = struct.unpack(">Q", self._need(8, 15))[0]
        mk = self._need(4, 15) if masked else None
        pl = self._need(ln, 15) if ln else b""
        if mk:
            pl = bytes(b ^ mk[i % 4] for i, b in enumerate(pl))
        if op == 0x9:
            self.send_frame(0xA, pl)
            return (0x9, pl)
        if op in (0x1, 0x2) and not fin:
            self.frag, self.fop = pl, op
            return (0x0, b"")
        if op == 0x0:
            self.frag += pl
            if not fin:
                return (0x0, b"")
            return (self.fop, self.frag)
        return (op, pl)

    def close(self):
        try:
            self.send_frame(0x8, b"")
        except Exception:
            pass
        try:
            self.s.close()
        except Exception:
            pass


def _loop():
    backoff = 3
    while not _stop.is_set():
        tok = wfmacct._token()
        if not _st["desired"] or not tok:
            _st.update(connected=False, authed=False)
            _stop.wait(2)
            continue
        ws = None
        try:
            host, port, tls = TARGET
            ws = _WS(host, port, tls, PATH, "https://warframe.market", "wfm")
            _st.update(connected=True, authed=False, err="")
            ws.send(json.dumps({"route": "@wfm|cmd/auth/signIn", "payload": {"token": tok}}))
            sent_for, sent_at, ping_at, authed = None, 0, time.time(), False
            while not _stop.is_set() and _st["desired"]:
                want = _st["desired"]
                if authed and (sent_for != want or time.time() - sent_at > DURATION * 0.75):
                    ws.send(json.dumps({"route": "@wfm|cmd/status/set", "payload": {"status": want, "duration": DURATION}}))
                    sent_for, sent_at = want, time.time()
                if time.time() - ping_at > 25:
                    ws.send_frame(0x9, b"")
                    ping_at = time.time()
                m = ws.recv(2.0)
                if m is None:
                    continue
                if m[0] == 0x8:
                    raise OSError("fechado pelo servidor")
                if m[0] != 0x1:
                    continue
                try:
                    j = json.loads(m[1].decode("utf-8"))
                except Exception:
                    continue
                r = str(j.get("route", ""))
                if r == "@wfm|cmd/auth/signIn:ok":
                    authed = True
                    _st["authed"] = True
                elif "signIn" in r and "error" in r.lower():
                    raise PermissionError("token recusado pelo servidor (entre de novo na aba Mercado)")
                elif r == "@wfm|event/status/set":
                    _st["last"] = (j.get("payload") or {}).get("status", "")
            backoff = 3
        except PermissionError as e:
            _st.update(err=str(e))
            _stop.wait(60)
        except Exception as e:
            _st.update(err="%s: %s" % (type(e).__name__, e))
            _stop.wait(backoff)
            backoff = min(backoff * 2, 60)
        finally:
            _st.update(connected=False, authed=False)
            if ws:
                ws.close()


def _ensure():
    if not _thr[0] or not _thr[0].is_alive():
        _stop.clear()
        _thr[0] = threading.Thread(target=_loop, daemon=True, name="wfm-presence")
        _thr[0].start()


def set_status(status):
    if status not in ("", "online", "ingame", "invisible"):
        raise wfmacct.WfmError("Status inválido.")
    if status and not wfmacct._token():
        raise wfmacct.WfmError("Entre na sua conta na aba Mercado primeiro.", 401)
    settings.update({"wfm_status": status})
    _st["desired"] = status
    if status:
        _ensure()
    return state()


def autostart():
    s = settings.get("wfm_status")
    if s and wfmacct._token():
        _st["desired"] = s
        _ensure()


def state():
    return dict(_st)
