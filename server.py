'''
SERVER (CS371 PROJECT FINAL)
Group Members:
	Phong Nguyen
	Tyler Brennan
	Lakin Miller
'''

import threading, socket, pickle, asyncio
import os, time, random

HOSTNAME = socket.gethostname()
PORTNO = 8080
PORTNO2 = 8888
ROOT_FOLDER = "root"
DWNLD_STATS = {}
SOCKS = []
def get_file_size_pickle(filePath: str) -> dict:
	# gets the pickled filesize of the path provided (used for DOWNLOAD command)
	data = {
		"DATASIZE": 0
	}
	filePath = os.path.normpath(filePath)
	if os.path.exists(filePath):
		with open(filePath,'rb') as handle:
			payload_data = pickle.dumps(handle.read()) # grab data and picklize it
			data['DATASIZE'] = len(payload_data)
	return data


def get_file_metadata(filePath: str) -> dict:
	## this function grabs some metadata from the requested file path
	metadata = {
		"FILENAME": "",
		"DATASIZE": 0,
		"TIMESTAMP": 0,
		"NUM_DOWNLOADS": 0,
	}
	metadata['FILENAME'] = os.path.split(filePath)[1] # grab just the filename
	with open(filePath,'rb') as handle:
		handle.seek(0,2)
		metadata['DATASIZE'] = handle.tell() # get filesize
	metadata['TIMESTAMP'] = os.path.getmtime(filePath) # get the timestamp of when the file was created/last modified (based on os)
	return metadata

def send_data(conn: socket.socket, filePath):
	# send data now
	file_path = os.path.normpath(filePath) # normalize the path to os standard
	with open(filePath,'rb') as handle:
		file_data = handle.read() # reads all the data from the file
	conn.send(pickle.dumps(file_data))
def receive_data(conn: socket.socket, data_length: int, prog_bar: bool = False):
	# we need to fully receive the data before we return it
	# data can be transmitted over several acks so loop until
	# the length of our data array is equal/ greater than to data_length
	data = bytearray()
	start_time = time.time() # to measure time taken for this download
	print(f"\rDownload percentage: {(len(data)/data_length)*100:.0f}%",end="") # progress bar
	while len(data) < data_length:
		data += conn.recv(data_length-len(data))
		print(f"\rDownload percentage: {(len(data)/data_length)*100:.0f}%",end="") # progress bar
	end_time = time.time() # end of download time
	avg_data_rate = (data_length/(end_time-start_time))/1048576 # average data speed by megabytes
	print() # pretty print the terminal
	return (data,start_time,end_time,avg_data_rate)
def init_download_stats() -> None:
	# creates a download stat entry for all files in the current directory
	file_list = os.listdir() # get list of all files in the directory
	file_meta_list = [get_file_metadata(file) for file in file_list] # create metadata for all files in file_list
	for file in file_meta_list:
		DWNLD_STATS[file['FILENAME']] = 0 # set all file downloads to 0

def listen_fn(conn: socket.socket) -> None:
	while True:
		message = conn.recv(2048)
		message = pickle.loads(message)
		print("Incoming message: ", message) # for debugging purposes, we can see all received messages
		if message['HEADER']['TYPE'] == "UPLOAD":
			## weve received an upload request!
			# tell the sender were ready for it!
			data_ack = {
				'HEADER': {
					"ID": random.randint(0,0xFFFFFFFF),
					"TYPE": "ACK",
					"ORIGIN_TYPE": "UPLOAD",
					"DATA_LOCATION": message['HEADER']['DATA_LOCATION']
				}
			}
			conn.send(pickle.dumps(data_ack)) # send the ack here

			payload, start_time, end_time, avg_data_rate  = receive_data(conn,message['HEADER']['DATASIZE']) # receive the file

			payload = pickle.loads(payload) # unserialize the data into its original form
			out_file_path = message['HEADER']['DATA_LOCATION'] # the file name from the request
			with open(os.path.normpath(out_file_path),'wb') as handle:
				handle.write(payload) # open the file handle and write to it

			file_ack = {
				# weve received the file, send an ack so client isnt high and dry
				# also send upload statistics
				'HEADER': {
					"ID": random.randint(0,0xFFFFFFFF),
					"TYPE": "ACK",
					"ORIGIN_TYPE": "FILE_RECEIVE",
					"FILENAME": message['HEADER']['DATA_LOCATION']
				},
				"DATA": {
					"FILE_TRANSFER_TOTAL": end_time-start_time,
					"AVG_DATA_RATE": avg_data_rate
				}
			}
			conn.send(pickle.dumps(file_ack))
			DWNLD_STATS[message['HEADER']['DATA_LOCATION']] = 0 # add this entry to the download stats
			# is this from a REQ_UPLOAD packet
			try:
				if message['HEADER']['ORIGIN_TYPE'] == "REQ_UPLOAD":
					# it is!
					# send a download request to the other client
					# get the other client, we need to find a new system as this is unreliable if other clients have connected and disconnected
					client2 = SOCKS[SOCKS.index(conn)^1]
					packet = {
						"HEADER": {
							"TYPE": "REQ_DOWNLOAD",
							"ORIGIN_TYPE": "REQ_UPLOAD",
							"DATA_LOCATION": message['HEADER']['DATA_LOCATION'],
							"FROM_SERVER": False
						}
					}
					client2.send(pickle.dumps(packet))
			except KeyError:
				# this message does not have a REQ_UPLOAD origin, just continue on
				pass
		elif message['HEADER']['TYPE'] == "DIR":
			## weve received a dir request!
			# we have to return all the files in the root directory
			file_list = os.listdir()
			file_meta_list = [get_file_metadata(file) for file in file_list]
			### CONSTRUCT THE ACTUAL PACKET AND TELL CLIENT HOW LARGE DATA IS ###
			ret_data = {
				"HEADER": {
					"TYPE": "DIR"
				},
				"DATA": file_meta_list,
				"AD_INFO": DWNLD_STATS
			}
			out_msg = pickle.dumps(ret_data)
			## CONSTRUCT ACK PACKET ##
			ack_data = {
				"HEADER": {
					"TYPE": "ACK",
					"ORIGIN_TYPE": "DIR",
					"DATASIZE": len(out_msg)
				}
			}
			time.sleep(0.05)
			conn.send(pickle.dumps(ack_data))
			time.sleep(0.05)
			conn.send(pickle.dumps(ret_data))
		elif message['HEADER']['TYPE'] == "DOWNLOAD":
			## weve received a dwnld request!
			# check if the file exists locally...
			for file in message['DATA']['FILELIST']:
				if os.path.exists(file):
					# the file exists!!!
					# first grab the file size
					meta = get_file_size_pickle(file)
					# send an ack with the file size so client can prepare
					try:
						FROM_SERVER = message['HEADER']['FROM_SERVER']
					except KeyError:
						FROM_SERVER = True
					init_ack = {
						'HEADER': {
							"ID": random.randint(0,0xFFFFFFFF),
							"TYPE": "ACK",
							"ORIGIN_TYPE": "DOWNLOAD",
							"FILENAME": file,
							"DATASIZE": meta['DATASIZE'],
							"FROM_SERVER": FROM_SERVER
						}
					}
					conn.send(pickle.dumps(init_ack))
					# now we wait for the client ack
					inc_msg = pickle.loads(conn.recv(2048))
					time.sleep(1)
					# client is ready, send data!
					send_data(conn,file)
					try:
						DWNLD_STATS[file] += 1
					except KeyError:
						DWNLD_STATS[file] = 1
				else:
					# the file doesnt exist!!
					# is client 2 connected?
					if len(SOCKS) == 1:
						# client 2 is not connected return an ERROR packet
						ack = {
							'HEADER': {
								"ID": random.randint(0,0xFFFFFFFF),
								"TYPE": "ERROR",
								"ORIGIN_TYPE": "DOWNLOAD",
								"ERROR_TYPE": "FILE_NOT_FOUND_SERVER"
							},
							'DATA': f"The file {file} does not exist on this server."
						}
						conn.send(pickle.dumps(ack))
					elif len(SOCKS) == 2:
						# a second client is connected, ask them to upload the file to the server
						client2 = SOCKS[SOCKS.index(conn)^1]
						#print(SOCKS)
						req = {
							'HEADER': {
								"ID": random.randint(0,0xFFFFFFFF),
								"TYPE": "REQ_UPLOAD",
								"DATA_LOCATION": file,

								"FROM_SERVER": False
							}
						}
						client2.send(pickle.dumps(req))
		elif message['HEADER']['TYPE'] == "ACK":
			'''
			if message['HEADER']['ORIGIN_TYPE'] == "MID_DWN":
				# this is coming from client 2, send the file back to client1
				client2 = SOCKS[SOCKS.index(conn)^1]
				time.sleep(0.05)
				# client2 is ready to send data!
				payload, start_time, end_time, avg_data_rate  = receive_data(conn,message['HEADER']['DATASIZE'])
				# save the file (kinda dumb but we have to delete it or something)
				with open(message['HEADER']['FILENAME'],'wb') as handle:
					handle.write(pickle.loads(payload))
				final_ack = {
					'HEADER': {
						"ID": random.randint(0,0xFFFFFFFF),
						"TYPE": "ACK",
						"ORIGIN_TYPE": "DOWNLOAD",
						"FILENAME": message['HEADER']['FILENAME'],
						"DATASIZE": message['HEADER']['DATASIZE'],
						"FROM_SERVER": False
					}
				}

				client2.send(pickle.dumps(final_ack))
				time.sleep(0.1)
				client2.send(payload)
			'''
			if message['HEADER']['ORIGIN_TYPE'] == "DOWNLOAD_FINISHED":
				if not message['HEADER']['FROM_SERVER']:
					os.remove(message['HEADER']['FILENAME'])
		elif message['HEADER']['TYPE'] == "DELETE":
			# delete the requested file and send an ack for it
			os.remove(message['HEADER']['FILENAME'])
			ack = {
				'HEADER': {
					"ID": random.randint(0,0xFFFFFFFF),
					"TYPE": "ACK",
					"ORIGIN_TYPE": "DELETE",
					"FILENAME": message['HEADER']['FILENAME']
				}
			}
			conn.send(pickle.dumps(ack))
		elif message['HEADER']['TYPE'] == "DISCONNECT":
			# a client is disconnecting, remove it from the SOCKS array
			SOCKS.pop(SOCKS.index(conn))
			print(f"Socket to {conn.laddr[0]}:{conn.laddr[1]} was closed.")
			conn.close()

		elif message['HEADER']['TYPE'] == "ERROR":
			if message['HEADER']['ERROR_TYPE'] == "FILE_NOT_FOUND_CLIENT2":
				client2 = SOCKS[SOCKS.index(conn)^1]
				client2.send(pickle.dumps(message))
def new_client(sock: socket.socket, addr):
	print(f"CONNECTED TO {addr}")
	listen_thread_1 = threading.Thread(target=listen_fn, args=(sock,))
	listen_thread_1.start()
def main() -> None:
	os.chdir(os.path.dirname(__file__))
	if not os.path.exists(ROOT_FOLDER):
		os.makedirs(ROOT_FOLDER)

	os.chdir(ROOT_FOLDER)

	init_download_stats()

	server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	server_sock.bind((HOSTNAME,PORTNO))
	print(f"Server hosted at {HOSTNAME}:{PORTNO}")
	server_sock.listen(2)

	while True:
		client_sock, client_addr = server_sock.accept()
		SOCKS.append(client_sock)
		new_client(client_sock,client_addr)
	server_sock.close()

if __name__ == "__main__":
	os.system('cls || clear') # clears terminal of excess data from vscode debugging
	main()
