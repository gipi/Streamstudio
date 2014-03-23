source = single("/streaming/video.ogv")

output.icecast(
        %ogg(%theora,%vorbis),
        host="localhost",
        port=8000,
        password="hackme",
        mount="/videostream",
        source)
