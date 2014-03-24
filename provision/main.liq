set("server.socket",true)
set("server.socket.path","/var/run/liquidsoap/liquid.sock")

source = single("/streaming/video.ogv")

output.icecast(
        %ogg(%theora,%vorbis),
        host="localhost",
        port=8000,
	user="othersource",
        password="hackmemore",
        mount="/videostream",
        source)
