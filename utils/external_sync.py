import socket

class External_Sync(object):
    def __init__(self, role, ip, port) -> None:
        self.role = role
        self.ip = ip
        self.port = port
        self.buffer_size = 1024
        # if self.role == "server":
        #     self.run_server()
        # else:
        #     self.run_client()

    def run_server(self):
        sync_received = False
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.ip, self.port))
            s.listen()
            conn, addr = s.accept()
            sync_received = True
            # with conn:
            #     print(f"Connected by {addr}")
            #     while True:
            #         data = conn.recv(self.buffer_size)
            #         print(data)
            #         if data == "1":
            #             sync_received = True
            #             # conn.sendall(data)
            #             break
            #         elif not data:
            #             break
        return sync_received


    def run_client(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.ip, self.port))
            s.sendall(b"1")
            # data = s.recv(self.buffer_size)

        # print(f"Received {data!r}")
