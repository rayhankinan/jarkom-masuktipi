import time
from socket import timeout as socket_timeout

from lib.argparse import Parser
from lib.connection import Connection
from lib.constant import (ACK_FLAG, FIN_FLAG, SYN_ACK_FLAG, SYN_FLAG,
                          TIMEOUT_LISTEN)
from lib.segment import Segment


class Client:
    def __init__(self):
        args = Parser(is_server=False)
        client_port, broadcast_port, pathfile_output = args.get_values()
        self.client_port: str = client_port
        self.broadcast_port: str = broadcast_port
        self.pathfile_output: str = pathfile_output.split("/")[-1]
        self.conn = Connection(
            broadcast_port=broadcast_port, port=client_port, is_server=False
        )
        self.segment = Segment()
        self.file = self.create_file()

    def connect(self):
        self.conn.send_data(
            self.segment.get_bytes(), (self.conn.ip, self.broadcast_port)
        )

    def three_way_handshake(self):
        while True:
            data, server_addr = None, ("127.0.0.1", self.broadcast_port)
            try:
                data, server_addr = self.conn.listen_single_segment(
                    TIMEOUT_LISTEN)
                self.segment.set_from_bytes(data)
                if self.segment.get_flag() == SYN_FLAG:
                    self.segment.set_flag(["SYN", "ACK"])
                    header = self.segment.get_header()
                    header["ack"] = header["seq"] + 1
                    header["seq"] = 0
                    print(
                        f"[!] [Server {server_addr[0]}:{server_addr[1]}] Sending SYN-ACK")
                    self.conn.send_data(self.segment.get_bytes(), server_addr)
                elif self.segment.get_flag() == SYN_ACK_FLAG:
                    print(
                        f"[!] [Server {server_addr[0]}:{server_addr[1]}] Resending SYN-ACK")
                    self.conn.send_data(self.segment.get_bytes(), server_addr)
                elif self.segment.get_flag() == ACK_FLAG:
                    print(
                        f"[!] [Server {server_addr[0]}:{server_addr[1]}] Received ACK")
                    print(
                        f"[!] [Server {server_addr[0]}:{server_addr[1]}] Handshake established"
                    )
                    break
                else:
                    print(f"[!] [Server {server_addr[0]}:{server_addr[1]}] Segment File Received, Resetting Connection")
                    self.segment.set_flag(["SYN", "ACK"])
                    header = self.segment.get_header()
                    header["ack"] = 1
                    header["seq"] = 0
                    print(f"[!] [Server {server_addr[0]}:{server_addr[1]}] Sending SYN-ACK")
                    self.conn.send_data(self.segment.get_bytes(), server_addr)
            except socket_timeout:
                if (self.segment.get_flag() == SYN_ACK_FLAG):
                    print(
                        f"[!] [Server {server_addr[0]}:{server_addr[1]}] [Timeout] ACK response timeout"
                    )
                    self.conn.send_data(self.segment.get_bytes(), server_addr)
                else:
                    print(
                        f"[!] [Server {server_addr[0]}:{server_addr[1]}] [Timeout] SYN response timeout"
                    )

    def sendACK(self, server_addr, ackNumber):
        response = Segment()
        response.set_flag(["ACK"])
        header = response.get_header()
        header["seq"] = ackNumber - 1
        header["ack"] = ackNumber
        response.set_header(header)
        self.conn.send_data(response.get_bytes(), server_addr)

    def listen_file_transfer(self):
        metadata_number = 2
        metadata_received = False
        request_number = 3
        data, server_addr = None, None
        while True:
            try:
                data, server_addr = self.conn.listen_single_segment(3)
                if server_addr[1] == self.broadcast_port:
                    self.segment.set_from_bytes(data)
                    if (
                            self.segment.valid_checksum()
                            and self.segment.get_header()["seq"] == metadata_number
                            and metadata_received == False
                    ):
                        payload = self.segment.get_payload()
                        metadata = payload.decode().split(",")
                        print(
                            f"[!] [Server {server_addr[0]}:{server_addr[1]}] Received Filename: {metadata[0]}, File Extension: {metadata[1]}, File Size: {metadata[2]}"
                        )
                        metadata_received = True
                        self.sendACK(server_addr, metadata_number)
                        continue
                    elif (
                        self.segment.valid_checksum()
                        and self.segment.get_header()["seq"] == request_number
                    ):
                        payload = self.segment.get_payload()
                        self.file.write(payload)
                        print(
                            f"[!] [Server {server_addr[0]}:{server_addr[1]}] Received Segment {request_number}"
                        )
                        print(
                            f"[!] [Server {server_addr[0]}:{server_addr[1]}] Sending ACK {request_number + 1}"
                        )
                        request_number += 1
                        self.sendACK(server_addr, request_number)
                        continue
                    elif self.segment.get_flag() == FIN_FLAG:
                        print(
                            f"[!] [Server {server_addr[0]}:{server_addr[1]}] Received FIN"
                        )
                        break
                    elif self.segment.get_header()["seq"] < request_number:
                        print(
                            f"[!] [Server {server_addr[0]}:{server_addr[1]}] Received Segment {self.segment.get_header()['seq']} [Duplicate]"
                        )
                    elif self.segment.get_header()["seq"] > request_number:
                        print(
                            f"[!] [Server {server_addr[0]}:{server_addr[1]}] Received Segment {self.segment.get_header()['seq']} [Out-Of-Order]"
                        )
                    else:
                        print(
                            f"[!] [Server {server_addr[0]}:{server_addr[1]}] Received Segment {self.segment.get_header()['seq']} [Corrupt]"
                        )
                else:
                    print(
                        f"[!] [Server {server_addr[0]}:{server_addr[1]}] Received Segment {self.segment.get_header()['seq']} [Wrong port]"
                    )
                self.sendACK(server_addr, request_number)
            except socket_timeout:
                print(
                    f"[!] [Server {server_addr[0]}:{server_addr[1]}] [Timeout] timeout error, resending prev seq num"
                )
                self.sendACK(server_addr, request_number)

        # sent FIN-ACK and wait for ACK to tearing down connection
        print(
            f"[!] [Server {server_addr[0]}:{server_addr[1]}] Sending FIN-ACK")
        # send FIN ACK
        finack = Segment()
        finack.set_header({
            "ack": request_number,
            "seq": request_number
        })
        finack.set_flag(["FIN", "ACK"])
        self.conn.send_data(finack.get_bytes(), server_addr)
        ack = False
        timeout = time.time() + TIMEOUT_LISTEN
        while not ack:
            try:
                data, server_addr = self.conn.listen_single_segment()
                ackSegment = Segment()
                ackSegment.set_from_bytes(data)
                if ackSegment.get_flag() == ACK_FLAG:
                    print(
                        f"[!] [Server {server_addr[0]}:{server_addr[1]}] Received ACK. Tearing down connection."
                    )
                    ack = True
            except socket_timeout:
                if (time.time() > timeout):
                    print(
                        f"[!] [Server {server_addr[0]}:{server_addr[1]}] [Timeout] waiting for too long, connection closed."
                    )
                    break
                print(
                    f"[!] [Server {server_addr[0]}:{server_addr[1]}] [Timeout] timeout error, resending FIN ACK."
                )
                self.conn.send_data(finack.get_bytes(), server_addr)
        # Finish get ack from server try to write file
        print(
            f"[!] [Server {server_addr[0]}:{server_addr[1]}] Data received successfuly"
        )
        print(
            f"[!] [Server {server_addr[0]}:{server_addr[1]}] Writing file to out/{self.pathfile_output}"
        )

    def create_file(self):
        try:
            file = open(f"out/{self.pathfile_output}", "wb")
            return file
        except FileNotFoundError:
            print(f"[!] {self.pathfile_output} doesn't exists. Exiting...")
            exit(1)

    def shutdown(self):
        self.file.close()
        self.conn.close_socket()


if __name__ == "__main__":
    main = Client()
    main.connect()
    main.three_way_handshake()
    main.listen_file_transfer()
    main.shutdown()
