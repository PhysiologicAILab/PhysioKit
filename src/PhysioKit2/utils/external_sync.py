import socket
import threading
from PySide6.QtCore import Signal, QThread, Signal
import time

class ServerThread(QThread):
    update = Signal(str)

    def __init__(self, ip, port, parent):
        # QThread.__init__(self, parent)
        super(ServerThread, self).__init__(parent=parent)

        self.stop_flag = False
        self.ip = ip
        self.port = port
        self.buffer_size = 1024
        self.server_socket = None
        self.client_connect_status = []
        self.signal_byte = b"1"
        self.connections = []  # Connection added to this list every time a client connects
        self.client_addresses = []

    def stop(self):
        self.stop_flag = True
        time.sleep(1)
        self.terminate()
        print("Server thread terminated...")


    def run(self):
        self.server_socket = socket.socket()
        self.server_socket.bind((self.ip, self.port))
        self.server_socket.listen(5)

        while not self.stop_flag:
            client_socket, addr = self.server_socket.accept()
            self.connections.append(client_socket)
            self.client_addresses.append(addr)
            self.client_connect_status.append(True)
            self.update.emit(f"Connection from {addr} has been established.")
            threading.Thread(target=self.manage_connections, args=(client_socket, addr)).start()

        self.server_socket.close()


    def manage_connections(self, client_socket, addr):
        while not self.stop_flag:
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

            
    def send_sync_to_client(self):
        for conn in self.connections:
            conn.sendall(self.signal_byte)


class ClientThread(QThread):
    connect_update = Signal(bool)
    sync_update = Signal(bool)

    def __init__(self, ip, port, parent):
        # QThread.__init__(self, parent)
        super(ClientThread, self).__init__(parent=parent)

        self.stop_flag = False
        self.wait_for_sync = False
        self.ip = ip
        self.port = port
        self.buffer_size = 1024
        self.client_conn = None
        self.signal_byte = b"1"


    def stop(self):
        self.stop_flag = True
        self.terminate()
        print("Client thread terminated...")


    def run(self):
        while not self.stop_flag:
            try:
                self.client_conn = socket.create_connection((self.ip, self.port))
                self.connect_update.emit(True)
           
                while not self.stop_flag:
                    if self.wait_for_sync:
                        data = self.client_conn.recv(self.buffer_size)
                        if data == self.signal_byte:
                            self.sync_update.emit(True)

                        elif not data:
                            self.sync_update.emit(False)
                            self.connect_update.emit(False)
                            time.sleep(1)
                    else:
                        time.sleep(1)
        
            except:
                self.connect_update.emit(False)
                # print("Connection could not be established... Retrying...")
                time.sleep(5)
            


