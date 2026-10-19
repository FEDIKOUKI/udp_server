"""
udp_server.py

Simple UDP echo/receiver server.

Usage:
  python udp_server.py --host 0.0.0.0 --port 9999

Bind to 0.0.0.0 to accept connections from any network interface on the machine.
To make it reachable from the Internet, you must have a public IP, or configure
your router to forward UDP traffic on the chosen port to this machine's local IP.

The server prints incoming messages and replies with an acknowledgement.
"""
import argparse
import socket
import sys
import threading
import signal


def handle_packet(data: bytes, addr, sock: socket.socket):
    text = data.decode(errors='replace')
    print(f"Received from {addr}: {text}")
    # simple acknowledgement
    reply = f"ACK: {len(data)} bytes".encode()
    try:
        sock.sendto(reply, addr)
    except Exception as e:
        print(f"Failed to send reply to {addr}: {e}")


def run_server(host: str, port: int, bufsize: int = 4096):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # allow quick reuse
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # set a short timeout so recvfrom doesn't block forever and we can
    # check for shutdown requests (Ctrl+C) in a timely manner
    sock.settimeout(1.0)

    try:
        sock.bind((host, port))
    except Exception as e:
        print(f"Failed to bind {host}:{port}: {e}")
        sys.exit(1)

    print(f"UDP server listening on {host}:{port}")

    # handle Ctrl+C gracefully
    stop_event = threading.Event()

    def signal_handler(sig, frame):
        print("Shutting down server...")
        stop_event.set()

    # SIGINT works on Windows for Ctrl+C; SIGTERM may not be present on all platforms
    signal.signal(signal.SIGINT, signal_handler)
    try:
        signal.signal(signal.SIGTERM, signal_handler)
    except Exception:
        # ignore if SIGTERM isn't available
        pass

    try:
        while not stop_event.is_set():
            try:
                data, addr = sock.recvfrom(bufsize)
            except socket.timeout:
                # timeout so we can check stop_event again
                continue
            except Exception as e:
                # If the socket was closed or interrupted, break the loop
                print(f"Socket error: {e}")
                break
            # handle in a separate thread so reply/small processing doesn't block
            t = threading.Thread(target=handle_packet, args=(data, addr, sock), daemon=True)
            t.start()
    finally:
        sock.close()


def parse_args():
    p = argparse.ArgumentParser(description="Simple UDP server")
    p.add_argument("--host", default="0.0.0.0", help="Host/IP to bind (default 193.95.82.45)")
    p.add_argument("--port", type=int, default=1030, help="UDP port to listen on (default 1030)")
    return p.parse_args()


if __name__ == '__main__':
    args = parse_args()
    run_server(args.host, args.port)
