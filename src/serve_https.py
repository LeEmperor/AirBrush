from http.server import HTTPServer, SimpleHTTPRequestHandler
import ssl

HOST = "0.0.0.0"
PORT = 8443

httpd = HTTPServer((HOST, PORT), SimpleHTTPRequestHandler)

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(certfile="cert.pem", keyfile="key.pem")
httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)

print(f"Serving HTTPS on https://{HOST}:{PORT}/")
httpd.serve_forever()