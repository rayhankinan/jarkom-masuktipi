
from lib.argparse import Parser
from lib.connection import Connection
from lib.segment import Segment


class Client:
    def __init__(self):
        args = Parser(is_server=False)
        client_port, broadcast_port, pathfile_output = args.get_values()
        self.client_port = client_port
        self.broadcast_port = broadcast_port
        self.pathfile_output = pathfile_output
        self.conn = Connection(broadcast_port=broadcast_port, port=client_port)

    def three_way_handshake(self):
        # Three Way Handshake, client-side
        print("[!] Initiating three way handshake...")
        self.conn.send_data(b"test", (self.conn.ip, self.broadcast_port))

    def listen_file_transfer(self):
        # File transfer, client-side
        pass


if __name__ == "__main__":
    main = Client()
    main.three_way_handshake()
    main.listen_file_transfer()
