class BandAPIException(Exception):
    def __init__(self, message):
        super(BandAPIException, self).__init__(message)
