import socket

class External_Sync(object):
    def __init__(self, role, ip, port) -> None:
        self.role = role
        self.ip = ip
        self.port = port
        self.buffer_size = 1024
        self.server_socket = None
        self.server_conn = None
        self.client_connect_status = False
        self.client_socket = None
        self.signal_byte = b"1"


    def start_accepting_client_connection(self):
        self.server_socket = socket.socket()
        self.server_socket.bind((self.ip, self.port))
        self.server_socket.listen()
        self.server_conn, addr = self.server_socket.accept()
        self.client_connect_status = True


    def send_sync_to_client(self):
        self.server_conn.sendall(self.signal_byte)


    def connect_with_server(self):
        self.client_socket = socket.create_connection((self.ip, self.port))


    def wait_for_server_sync(self) -> bool:
        sync = False
        while True:
            data = self.client_socket.recv(self.buffer_size)
            if data == self.signal_byte:
                sync = True
                break 
            elif not data:
                break

        return sync
