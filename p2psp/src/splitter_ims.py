# This code is distributed under the GNU General Public License (see
# THE_GENERAL_GNU_PUBLIC_LICENSE.txt for extending this information).
# Copyright (C) 2014, the P2PSP team.
# http://www.p2psp.org

# {{{ Imports

from __future__ import print_function
import sys
import socket
import threading
import struct
from color import Color
import common
import time
from _print_ import _print_

# }}}

# IMS: IP Multicast Set of rules.
class Splitter_IMS(threading.Thread):
    # {{{

    # {{{ Class "constants"

    # {{{ The buffer_size (in chunks). The buffer_size should be
    # proportional to the bit-rate (remember that the latency is also
    # proportional to the buffer_size).
    # }}}
    BUFFER_SIZE = 256

    # {{{ Channel served by the streaming source.
    # }}}
    CHANNEL = "Big_Buck_Bunny_small.ogv"

    # {{{ The chunk_size (in bytes) depends mainly on the network
    # technology and should be selected as big as possible, depending
    # on the MTU and the bit-error rate.
    # }}}
    CHUNK_SIZE = 1024

    # {{{ Number of chunks of the header.
    # }}}
    HEADER_SIZE = 10

    # {{{ The unicast IP address of the splitter server.
    # }}}
    #SPLITTER_ADDR = "127.0.0.1" # No por ahora

    # {{{ Port used to serve the peers (listening port).
    # }}}
    PORT = 4552

    # {{{ The host where the streaming server is running.
    # }}}
    SOURCE_ADDR = "127.0.0.1"

    # {{{ Port where the streaming server is listening.
    # }}}
    SOURCE_PORT = 8000

    # {{{ Port where the splitter is listening a new source stream.
    # }}}
    SOURCE_PORT_IN = 8080

    # {{{ A password is required to send a stream to the splitter.
    # Default password: hackme (MD5)
    # }}}
    SOURCE_PASS = "23b4222d2613a2765d4d432d2d65e88e"

    # {{{ The multicast IP address of the team, used to send the chunks.
    # }}}
    MCAST_ADDR = "224.0.0.1" # All Systems on this subnet
    #MCAST_ADDR = "224.1.1.1"

    # }}}

    videoFile = None

    def __init__(self):
        # {{{

        threading.Thread.__init__(self)

        self.print_the_module_name()
        print("Buffer size (in chunks) =", self.BUFFER_SIZE)
        print("Chunk size (in bytes) =", self.CHUNK_SIZE)
        print("Channel =", self.CHANNEL)
        print("Header size (in chunks) =", self.HEADER_SIZE)
        #print("Splitter address =", self.SPLITTER_ADDR) # No ahora
        print("Listening (and multicast) port =", self.PORT)
        print("Source IP address =", self.SOURCE_ADDR)
        print("Source port =", self.SOURCE_PORT)
        print("Multicast address =", self.MCAST_ADDR)
        print("Source port in =", self.SOURCE_PORT_IN)

        # {{{ An IMS splitter runs 2 threads. The main one serves the
        # chunks to the team. The other controls peer arrivals. This
        # variable is true while the player is receiving data.
        # }}}
        self.alive = True

        # {{{ Number of the served chunk.
        # }}}
        self.chunk_number = 0

        # {{{ Used to listen to the incomming peers.
        # }}}
        self.peer_connection_socket = ""

        # {{{ Used to listen the team messages.
        # }}}
        self.team_socket = ""

        # {{{ Used to talk to the source (streaming server HTTP)
        # }}}
        self.source_socket = ""

        # {{{ The change is automatic (do not touch)
        #    mode = 0 to streaming server
        #    mode = 1 to listen a streaming
        # }}}
        self.mode = 0

        # {{{ Used to receive a stream from the source (via socket TCP)
        # }}}
        self.source_socket_in = ""

        # {{{ The video header.
        # }}}
        self.header = ""

        # {{{ Some other useful definitions.
        # }}}
        self.source = (self.SOURCE_ADDR, self.SOURCE_PORT)
        self.GET_message = 'GET /' + self.CHANNEL + ' HTTP/1.1\r\n'
        self.GET_message += '\r\n'
        self.chunk_number_format = "H"
        self.mcast_channel = (self.MCAST_ADDR, self.PORT)

        self.recvfrom_counter = 0
        self.sendto_counter = 0

        self.header_load_counter = 0


        # }}}

    def print_the_module_name(self):
        # {{{

        sys.stdout.write(Color.yellow)
        print("Splitter IMS")
        sys.stdout.write(Color.none)

        # }}}

    def send_the_header(self, peer_serve_socket):
        # {{{

        _print_("Sending a header of", len(self.header), "bytes")
        try:
            peer_serve_socket.sendall(self.header)
        except:
            pass

        # }}}

    def send_the_buffer_size(self, peer_serve_socket):
        # {{{

        if __debug__:
            print("Sending a buffer_size of", self.BUFFER_SIZE, "bytes")
        message = struct.pack("H", socket.htons(self.BUFFER_SIZE))
        try:
            peer_serve_socket.sendall(message)
        except:
            pass

        # }}}

    def send_the_chunk_size(self, peer_serve_socket):
        # {{{

        if __debug__:
            print("Sending a chunk_size of", self.CHUNK_SIZE, "bytes")
        message = struct.pack("H", socket.htons(self.CHUNK_SIZE))
        try:
            peer_serve_socket.sendall(message)
        except:
            pass

        # }}}

    def send_the_mcast_channel(self, peer_serve_socket):
        # {{{

        if __debug__:
            print("Communicating the multicast channel", (self.MCAST_ADDR, self.PORT))
        message = struct.pack("4sH", socket.inet_aton(self.MCAST_ADDR), socket.htons(self.PORT))
        try:
            peer_serve_socket.sendall(message)
        except:
            pass

        # }}}

    def send_the_header_size(self, peer_serve_socket):
        # {{{

        if __debug__:
            print("Communicating the header size", self.HEADER_SIZE)
        message = struct.pack("H", socket.htons(self.HEADER_SIZE))
        try:
            peer_serve_socket.sendall(message)
        except:
            pass

        # }}}

    def send_configuration(self, sock):
        # {{{

        self.send_the_mcast_channel(sock)
        self.send_the_header_size(sock)
        self.send_the_chunk_size(sock)
        self.send_the_header(sock)
        self.send_the_buffer_size(sock)

        # }}}

    def handle_a_peer_arrival(self, connection):
        # {{{ Handle the arrival of a peer. When a peer want to join a
        # team, first it must establish a TCP connection with the
        # splitter.

        serve_socket = connection[0]
        sys.stdout.write(Color.green)
        print(serve_socket.getsockname(), '\b: accepted connection from peer', \
              connection[1])
        sys.stdout.write(Color.none)
        self.send_configuration(serve_socket)
        serve_socket.close()

        # }}}

    def handle_arrivals(self):
        # {{{

        while self.alive:
            peer_serve_socket, peer = self.peer_connection_socket.accept()
            threading.Thread(target=self.handle_a_peer_arrival, args=((peer_serve_socket, peer), )).start()

        # }}}

    def setup_peer_connection_socket(self):
        # {{{ Used to listen to the incomming peers.

        self.peer_connection_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # This does not work in Windows systems.
            self.peer_connection_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except: # Falta averiguar excepcion
            pass

        try:
            #self.peer_connection_socket.bind((socket.gethostname(), self.PORT))
            self.peer_connection_socket.bind(('', self.PORT))
        except: # Falta averiguar excepcion
            raise

        # {{{ Set the connection queue to the max!
        # }}}
        self.peer_connection_socket.listen(socket.SOMAXCONN)

        # }}}

    def setup_team_socket(self):
        # {{{ Used to talk with the peers of the team. In this case,
        # it corresponds to a multicast channel.

        self.team_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

        self.team_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        try:
            # This does not work in Windows systems !!
            self.team_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except:
            pass
        try:
            #self.team_socket.bind((socket.gethostname(), self.PORT))
            self.team_socket.bind(('', self.PORT))
        except:
            raise

        # }}}

    def request_the_video_from_the_source(self):
        # {{{ Request the video using HTTP from the source node (Icecast).

        self.source_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if __debug__:
            print(self.source_socket.getsockname(), 'connecting to the source', self.source, '...')
        self.source_socket.connect(self.source)
        if __debug__:
            print(self.source_socket.getsockname(), 'connected to', self.source)
        self.source_socket.sendall(self.GET_message)
        _print_(self.source_socket.getsockname(), 'GET_message =', self.GET_message)

        # }}}

    def configure_sockets(self):
        # {{{ setup_peer_connection_socket()

        try:
            self.setup_peer_connection_socket()
        except Exception, e:
            print(e)
            print(self.peer_connection_socket.getsockname(), "\b: unable to bind the port ", self.PORT)
            sys.exit('')

        # }}}

        # {{{ setup_team_socket()

        try:
            self.setup_team_socket()
        except Exception, e:
            print(e)
            print(self.team_socket.getsockname(), "\b: unable to bind", (socket.gethostname(), self.PORT))
            sys.exit('')

        # }}}

    def load_the_video_header(self):
        # {{{ Load the video header.

        for i in xrange(self.HEADER_SIZE):
            self.header += self.receive_next_chunk()

        # }}}

    def receive_next_chunk(self):
        # {{{

        chunk = self.source_socket.recv(self.CHUNK_SIZE)

        prev_size = 0
        while len(chunk) < self.CHUNK_SIZE:
            if len(chunk) == prev_size:
                # This section of code is reached when the source streaming
                # server or source via socket finishes a stream and starts with
                # the following one.
                if len(chunk) != 0:
                    return chunk

                print("No data in the server!")

                if (self.mode == 0):
                    print ("Reload stream from streaming server")
                    sys.stdout.flush()
                    self.mode = 0
                    self.source_socket.close()
                    time.sleep(1)
                    self.source_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.source_socket.connect(self.source)
                    self.source_socket.sendall(self.GET_message)
                else:
                    print ("Stream from socket")
                    self.mode = 0
                    self.source_socket_in.sendall(self.SOURCE_PASS)
                    self.source_socket = self.source_socket_in

                self.header = ""
                self.header_load_counter = self.HEADER_SIZE
                chunk = ""

                #_print_("1: header_load_counter =", self.header_load_counter)

            prev_size = len(chunk)
            chunk += self.source_socket.recv(self.CHUNK_SIZE - len(chunk))

        return chunk

        # }}}

    def receive_chunk(self):
        # {{{

        chunk = self.receive_next_chunk()
        #_print_ ("2: header_load_counter =", self.header_load_counter)
        if self.header_load_counter > 0:
            self.header += chunk
            self.header_load_counter -= 1
            print("Loaded", len(self.header), "bytes of header")
            #_print_("3: header_load_counter =", self.header_load_counter)

        self.recvfrom_counter += 1

        return chunk

        # }}}

    def send_chunk(self, message, peer):
        # {{{

        self.team_socket.sendto(message, peer)

        #if __debug__:
            #print('%5d' % self.chunk_number, Color.red, '->', Color.none, peer)
            #sys.stdout.flush()

        self.sendto_counter += 1

        # }}}

    def receive_the_header(self):
        # {{{

        self.configure_sockets()
        self.request_the_video_from_the_source()
        self.load_the_video_header()

        # }}}

    def listen_a_video_source(self):
        # {{{ When a video stream is received, the source is replaced by this stream.

        source_socket_in = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # This does not work in Windows systems !!
            source_socket_in.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except:
            pass
        source_socket_in.bind(('', self.SOURCE_PORT_IN))
        source_socket_in.listen(1)

        while (1):
            if (self.mode == 0):
                self.source_socket_in, addr = source_socket_in.accept()
                print ('A new source is connected in:', addr)

                data = self.source_socket_in.recv(1024)
                print ('Pass from source:', data)
                print ('Right pass:', self.SOURCE_PASS)

                if (data == self.SOURCE_PASS):
                    print ('correct password!')
                    self.mode = 1
                else:
                    print ('wrong password')
                    self.mode = 0
                    self.source_socket_in.close()

        # }}}

    def set_video_source(self, file):
        self.videoFile = file

    def read_video_chunk(self, length):
        read_data = self.videoFile.read(length)
        read_amount = len(read_data)
        if read_data < self.CHUNK_SIZE:
            read_data += self.read_video_chunk(self.CHUNK_SIZE-read_amount)
        return read_data

    def run(self):
        # {{{

        self.receive_the_header()

        print(self.peer_connection_socket.getsockname(), "\b: waiting for a peer ...")
        self.handle_a_peer_arrival(self.peer_connection_socket.accept())
        threading.Thread(target=self.handle_arrivals).start()
        threading.Thread(target=self.listen_a_video_source).start()

        message_format = self.chunk_number_format + str(self.CHUNK_SIZE) + "s"
        #_print_("4: header_load_counter =", self.header_load_counter)
        while self.alive:
            if self.videoFile is not None:
                video_chunk = self.read_video_chunk(self.CHUNK_SIZE)
                message = struct.pack(message_format, socket.htons(self.chunk_number), video_chunk)
                self.send_chunk(message, self.mcast_channel)
                self.chunk_number = (self.chunk_number + 1) % common.MAX_CHUNK_NUMBER
        # }}}
    # }}}
