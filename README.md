# CS371 Socket Programming Assignment
A repository for storing my group's socket programming assignment
The goal of this project was to create a socket-based client/server program. This program acts like a file-sharing server and is able to connect to two clients simultaneously.

## Server:
  The server program only displays incoming messages and the status of files being downloaded from clients.

## Client:
There are five commands available for use on the client.

### CONNECT:
  * Syntax: CONNECT {HOSTNAME} {PORT NUMBER}
  * Connects to a server hosted at the provided hostname and port number.
### DIR:
  * Syntax: DIR
  
  * Provides a list of all the files on the currently connected server.
  Each file entry shows the file size, file creation date, and times the file was downloaded.
 
### DOWNLOAD:
  * Syntax: DOWNLOAD {filename} [file2 file3 file4 ...]
  * Downloads the file(s) from the server. If the server does not have the requested file(s) and a second client is connected, it will ask the second client for the file if it has it.

### DELETE:
  * Syntax: DELETE {filename}
  * Deletes the specified file from the server.
 
 ### UPLOAD:
  * Syntax: UPLOAD {filename}
  * Uploads the specified file to the server.
