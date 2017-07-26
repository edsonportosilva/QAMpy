import zmq
import numpy as np
import msgpack
import msgpack_numpy as msgp_npy
from .phaserecovery import blindphasesearch


def pack_array(A):
    return msgpack.packb(A, default=msgp_npy.encode)

def unpack_array(A):
    out = msgpack.unpackb(A, object_hook=msgp_npy.decode)
    if isinstance(out, dict):
        outn = {}
        for k, v in out.items():
            if isinstance(k, bytes):
                outn[k.decode("utf-8")] = v
            else:
                outn[k] = v
        return outn
    else:
        return out

def send_array(socket, A, flags=0, copy=True, track=False):
    socket.send(pack_array(A), flags=flags, copy=copy, track=track)

def recv_array(socket, flags=0, copy=True, track=False):
    return unpack_array(socket.recv(flags=flags, copy=copy, track=track))

class PPWorker(object):
    def __init__(self, send_url, receive_url, context=None):
        self.context = context or zmq.Context.instance()
        self.send_socket = self.context.socket(zmq.PUSH)
        self.send_socket.connect(send_url)
        self.receive_socket = self.context.socket(zmq.PULL)
        self.receive_socket.connect(receive_url)

    def send_msg(self, msg, success=b"OK"):
        self.send_socket.send_multipart([success, pack_array(A)])

    def recv_msg(self):
        header, msg = self.collect_socket.recv_multipart()
        return header, unpack_array(msg)

    def process(self):
        header, msg = self.recv_msg()
        try:
            result = getattr(self, header)(**msg)
            success = b"OK"
        except Exception as err:
            success = b"ERR"
            result = err.encode("ascii")
        self.send_msg(result, success)

    def run(self):
        while True:
            self.process()
        self.socket.close()

class RepWorker(object):
    def __init__(self, url, context=None):
        self.context = context or zmq.Context.instance()
        self.socket = self.context.socket(zmq.REP)
        self.socket.connect(url)
        print("started on %s"%url)

    def send_msg(self, msg, success=b"OK"):
        self.socket.send_multipart([success, pack_array(msg)])

    def recv_msg(self):
        header, msg = self.socket.recv_multipart()
        return header, unpack_array(msg)

    def process(self):
        header, msg = self.recv_msg()
        try:
            result = getattr(self, header.decode("ascii"))(msg)
            success = b"OK"
        except Exception as err:
            success = b"ERR"
            result = repr(err).encode("ascii")
        self.send_msg(result, success)

    def run(self):
        while True:
            self.process()
            #self.recv_msg()
        #self.socket.close()


class DataDealer(object):
    def __init__(self, url, port=None, context=None):
        self.context = context or zmq.Context.instance()
        self.socket = self.context.socket(zmq.DEALER)
        if port == None:
            self.port = self.socket.bind_to_random_port(url, min_port=5000, max_port=5100)
        else:
            self.socket.bind(u"{}:{}".format(url, port))
            self.port = port

    def send_msg(self, header, msg, identity=None):
        msg = pack_array(msg)
        if identity is None:
            self.socket.send_multipart([b"", header, msg])
            #self.socket.send_multipart([b"", header])
        else:
            self.socket.send_multipart([identity, b"", header, msg])

    def recv_msg(self):
        msg = self.socket.recv_multipart()
        if msg[0] == b"":
            if msg[1] == b"OK":
                return unpack_array(msg[2])
            else:
                raise Exception(msg[2:])
        else:
            pass

class ResultSink(object):
    def __init__(self, url, port=None, context=None):
        self.context = context or zmq.Context.instance()
        self.socket = self.context.socket(zmq.PULL)
        if port is None:
            self.socket.bind_to_random_port(url)
        else:
            self.socket.bind(url+":"+port)


class PhRecWorker(RepWorker):
    def do_phase_rec(self, pdict):
        id = pdict['id']
        E = pdict['data']
        M = pdict['Mtestangles']
        syms = pdict['symbols']
        N = pdict['N']
        Eout, ph = blindphasesearch(E, M, syms, N)
        return {'Eout':Eout, 'ph':ph, 'id': id}



