from socket import SHUT_RDWR
import socket
import threading

class External_Sync(object):
    def __init__(self, role, ip, port) -> None:
        self.role = role
        self.ip = ip
        self.port = port
        self.buffer_size = 1024
        self.server_socket = None
        self.client_socket = None
        self.client_connect_status = []
        self.client_conn = None
        self.signal_byte = b"1"
        self.connections = []  # Connection added to this list every time a client connects
        self.client_addresses = []

    def start_accepting_client_connection(self):
        self.server_socket = socket.socket()
        self.server_socket.bind((self.ip, self.port))
        self.server_socket.listen(5)

        while True:
            client_socket, addr = self.server_socket.accept()
            self.connections.append(client_socket)
            self.client_addresses.append(addr)
            self.client_connect_status.append(True)
            threading.Thread(target=self.manage_connections, args=(client_socket, addr)).start()

    def manage_connections(self, client_socket, addr):

        print(f"Connection from {addr} has been established.")
        while True:
            try:
                msg = client_socket.recv(1024)
            except ConnectionError:
                print(f"Connection from {addr} has been lost.")
                if client_socket in self.connections:
                    self.connections.remove(client_socket)
                return
            if len(msg.decode('utf-8')) > 0:
                print(msg.decode("utf-8"))
            for connection in self.connections:  # iterates through the connections array and sends message to each one
                msgbreak = msg
                try:
                    connection.send(bytes(str(msgbreak.decode("utf-8")), "utf-8"))
                except ConnectionError:
                    print(f"Unable to reach client with socket {connection}")
                    if connection in self.connections:
                        self.connections.remove(connection)

        # try:
        #     self.server_socket.shutdown(SHUT_RDWR)
        #     self.server_socket.close()
        # except Exception:
        #     pass


    def send_sync_to_client(self):
        for conn in self.connections:
            conn.sendall(self.signal_byte)


    def connect_with_server(self):
        status = False
        try:
            self.client_conn = socket.create_connection((self.ip, self.port))
            status = True
        except:
            print("Connection could not be established... Please retry...")
        return status


    def wait_for_server_sync(self) -> bool:
        sync = False
        while True:
            data = self.client_conn.recv(self.buffer_size)
            if data == self.signal_byte:
                sync = True
                break 
            elif not data:
                break

        return sync
