'''
CLIENT (CS371 PROJECT FINAL)
Group Members:
	Phong Nguyen
	Tyler Brennan
	Lakin Miller
'''
import threading, socket, pickle, asyncio
import os, sys, time, re, random
from beautifultable import BeautifulTable

ROOT_FOLDER = "root_client"
def get_file_metadata(filePath) -> dict:
	# this function grabs the filedata size and returns the size of that file as pickle data
	# specifically for upload command
	data = {
		'DATASIZE': 0
	}
	filePath = os.path.normpath(filePath)
	if os.path.exists(filePath):
		with open(filePath,'rb') as handle:
			# read all file data and pickleize it
			payload_data = pickle.dumps(handle.read()) # grab data and picklize it
			data['DATASIZE'] = len(payload_data)
	return data

def print_dir(data: list, ad_info: dict) -> None:
	# print out the dir data we received from the server into a table
	table = BeautifulTable()
	table.columns.header = ["Filename","File size","Upload Time","Number of Downloads"]
	for file in data:
		table.rows.append([file['FILENAME'],file['DATASIZE'],time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(file['TIMESTAMP'])),ad_info[file['FILENAME']]])
	print()
	print(table)
	print(">> ",end="", flush=True)

def send_data(conn: socket.socket, message):
	# server waiting on file to be uploaded
	# send data now
	file_path = os.path.normpath(message['HEADER']['DATA_LOCATION'])
	with open(message['HEADER']['DATA_LOCATION'],'rb') as handle:
		file_data = handle.read()
	start_time = time.time()
	conn.send(pickle.dumps(file_data))
	end_time = time.time()
	print(end_time-start_time)
def receive_data(conn: socket.socket, data_length: int, prog_bar: bool = False):
	# we need to fully receive the data before we return it
	# data can be transmitted over several acks so
	data = bytearray()
	start_time = time.time()
	while len(data) < data_length:
		data += conn.recv(data_length-len(data))
		print(f"\rDownload percentage: {(len(data)/data_length)*100:.0f}%",end="")
	end_time = time.time()
	avg_data_rate = (data_length/(end_time-start_time))/1048576
	print()
	return (data,start_time,end_time,avg_data_rate)
def message_handler(conn, message):
	match message['HEADER']['TYPE']:
		case "ACK":
			match message['HEADER']['ORIGIN_TYPE']:
				case "DOWNLOAD":
					# weve received an ACK from a DOWNLOAD packet
					# tell the server we are ready!
					out_msg = {
						'HEADER': {
							"ID": random.randint(0,0xFFFFFFFF),
							"TYPE": "ACK",
							"ORIGIN_TYPE": "DOWNLOAD",
							"FROM_SERVER": True
						}
					}
					conn.send(pickle.dumps(out_msg))

					# receive data and write to file
					payload, start_time, end_time, avg_data_rate = receive_data(conn,message['HEADER']['DATASIZE'])
					with open("transfer_stats.txt",'a+') as txt_handle:
						txt_handle.write(f"\n{message['HEADER']['FILENAME']} took {end_time-start_time:.6f} seconds to download. The average data transfer rate was {avg_data_rate} megabytes per second")
					with open(message['HEADER']['FILENAME'],'wb') as handle:
						handle.write(pickle.loads(payload))
					print(f"{message['HEADER']['FILENAME']} was downloaded!")

					# tell the server we received the file

					del_ack = {
						'HEADER': {
							"ID": random.randint(0,0xFFFFFFFF),
							"TYPE": "ACK",
							"ORIGIN_TYPE": "DOWNLOAD_FINISHED",
							"FILENAME": message['HEADER']['FILENAME'],
							"FROM_SERVER": message['HEADER']['FROM_SERVER']
						}
					}
					time.sleep(0.05)
					conn.send(pickle.dumps(del_ack))
					print(">> ",end="", flush=True)
				case "UPLOAD":
					# weve received an ACK from an UPLOAD packet
					# send the requested data from the file path
					send_data(conn, message)
				case "DIR":
					## weve receive an ACK from a DIR packer
					# get ready to receive the actual data
					message = pickle.loads(conn.recv(message['HEADER']['DATASIZE']))
					print_dir(message['DATA'],message['AD_INFO'])
				case "DELETE":
					## weve received an ACK from a DELETE packet
					print(f"{message['HEADER']['FILENAME']} was deleted!")
					print(">> ",end="", flush=True)
				case "FILE_RECEIVE":
					## server had received some file we uploaded, cool
					print()
					print(f"{message['HEADER']['FILENAME']} was successfully uploaded!")
					with open("transfer_stats.txt",'a+') as txt_handle:
						txt_handle.write(f"\n{message['HEADER']['FILENAME']} took {message['DATA']['FILE_TRANSFER_TOTAL']:.6f} seconds to upload. The average data transfer rate was {message['DATA']['AVG_DATA_RATE']} megabytes per second")
					print(">> ",end="",flush=True)
		case "DOWNLOAD":
			# we got a download request from the server
			if os.path.exists(message['HEADER']['DATA_LOCATION']):
				# the file exists locally send an ack with file meta
				file_meta = get_file_metadata(message['HEADER']['DATA_LOCATION'])
				ack = {
					'HEADER': {
						"ID": random.randint(0,0xFFFFFFFF),
						"TYPE": "ACK",
						"ORIGIN_TYPE": "MID_DWN",
						"FILENAME": message['HEADER']['DATA_LOCATION'],
						"DATASIZE": file_meta['DATASIZE'],
						"FROM_SERVER": message['HEADER']['FROM_SERVER']
					}
				}
				time.sleep(0.1)
				conn.send(pickle.dumps(ack))
				time.sleep(0.25)
				send_data(conn,message)
			else:
				ack = {
					'HEADER': {
						"ID": random.randint(0,0xFFFFFFFF),
						"TYPE": "ERROR",
						"ORIGIN_TYPE": "DOWNLOAD",
						"ERROR_TYPE": "FILE_NOT_FOUND_CLIENT2"
					},
					'DATA': f"The file {message['HEADER']['DATA_LOCATION']} does not exist on this server/client."
				}
				conn.send(pickle.dumps(ack))
		case "REQ_UPLOAD":
			if os.path.exists(message['HEADER']['DATA_LOCATION']):
				meta = get_file_metadata(message['HEADER']['DATA_LOCATION'])
				msg = {
					"HEADER": {
						"TYPE": "UPLOAD",
						"ORIGIN_TYPE": "REQ_UPLOAD",
						"DATA_LOCATION": message['HEADER']['DATA_LOCATION'],
						"DATASIZE": meta['DATASIZE'],
						"FROM_SERVER": message['HEADER']['FROM_SERVER']
					}
				}
				conn.send(pickle.dumps(msg))
			else:
				msg = {
					"HEADER": {
						"TYPE": "ERROR",
						"ORIGIN_TYPE": "REQ_UPLOAD",
						"ERROR_TYPE": "FILE_NOT_FOUND_CLIENT2"
					},
					"DATA": "This file was not found on the server."
				}
				conn.send(pickle.dumps(msg))
		case "REQ_DOWNLOAD":
			msg = {
				"HEADER": {
					"TYPE": "DOWNLOAD",
					"ORIGIN_TYPE": "REQ_DOWNLOAD",
					"FROM_SERVER": message['HEADER']['FROM_SERVER']
				},
				"DATA": {
					"FILELIST": [message['HEADER']['DATA_LOCATION']]
				}
			}
			conn.send(pickle.dumps(msg))
		case "ERROR":
			# uh oh... some error occured...
			print(message['DATA'])
			print(">> ",end="",flush=True)
def listen_fn(conn: socket.socket) -> None:
	while True:
		message = conn.recv(2048)
		message = pickle.loads(message)
		data = message_handler(conn, message)

def talking_fn(conn: socket.socket) -> None:
	## here we are connected to the server.
	# start actual terminal
	print(f"Connected successfully")
	while True:
		our_message = input(">> ")
		args = [arg.strip('"') for arg in re.findall("(?:\".*?\"|\S)+", our_message)]
		if len(args) == 0:
			args = [None]
		match args[0]:
			case "UPLOAD":
				# create first packet to be sent
				meta = get_file_metadata(args[1])
				msg = {
					"HEADER": {
						"TYPE": "UPLOAD",
						"DATA_LOCATION": args[1],
						"DATASIZE": meta['DATASIZE']
					}
				}
				out_msg = pickle.dumps(msg)
				conn.send(out_msg)
			case "DIR":
				# show all file contents in the current dir
				msg = {
					"HEADER": {
						"TYPE": "DIR"
					}
				}
				out_msg = pickle.dumps(msg)
				conn.send(out_msg)
			case "DOWNLOAD":
				# download a file from server
				msg = {
					"HEADER": {
						"TYPE": "DOWNLOAD"
					},
					"DATA": {
						"FILELIST": args[1:]
					}
				}
				out_msg = pickle.dumps(msg)
				conn.send(out_msg)
			case "DELETE":
				msg = {
					"HEADER": {
						"TYPE": "DELETE",
						"FILENAME": args[1]
					}
				}
				out_msg = pickle.dumps(msg)
				conn.send(out_msg)
			case "DISCONNECT":
				msg = {
					"HEADER": {
						"TYPE": "DISCONNECT"
					}
				}
				conn.send(pickle.dumps(msg))
				conn.close()
				return
			case None:
				pass

def connect(HOSTNAME: str, PORTNO: int) -> threading.Thread:
	conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	conn.connect((HOSTNAME,PORTNO))
	listen_thread = threading.Thread(target=listen_fn, args=(conn,))
	talking_thread = threading.Thread(target=talking_fn, args=(conn,))
	listen_thread.start()
	talking_thread.start()
	listen_thread.join()
	talking_thread.join()
	return (listen_thread, talking_thread)
def upload() -> None:
	pass
def download() -> None:
	pass
def delete() -> None:
	pass
def dir() -> None:
	pass

def main():
	os.chdir(os.path.dirname(__file__))
	if not os.path.exists(ROOT_FOLDER):

		os.makedirs(ROOT_FOLDER)
	os.chdir(ROOT_FOLDER)
	while True:
		command = input(">> ")
		argv = command.split()
		if argv[0] == "CONNECT":
			HOSTNAME = argv[1]
			if HOSTNAME == "localhost":
				HOSTNAME = socket.gethostname()
			PORTNO = int(argv[2])
			try:
				connect(HOSTNAME,PORTNO)
			except ConnectionRefusedError:
				print("This connection was refused.")
		elif argv[0] == "EXIT":
			sys.exit()
		else:
			print()
if __name__ == "__main__":
	os.system('cls || clear') # clears terminal of excess data from vscode debugging
	main()
